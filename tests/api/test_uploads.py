"""Bounded uploads and a responsive desk while a file indexes."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from orbe.api.app import build_app
from orbe.api.routes import _read_within_limit
from orbe.application.reading import DossierIndexer, DossierReader
from orbe.domain.errors import UnreadableDossier
from orbe.domain.models import IndexedFile
from tests.support import MemoryHistory, ScriptedChain, ScriptedStore, allow_key, settings


class _CappedUpload:
    """An upload stream that counts how many bytes were pulled before it stopped."""

    def __init__(self, total: int, chunk: int) -> None:
        self._remaining = total
        self._chunk = chunk
        self.served = 0

    async def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        step = min(size if size > 0 else self._chunk, self._chunk, self._remaining)
        self._remaining -= step
        self.served += step
        return b"x" * step


def test_read_within_limit_stops_before_reading_the_whole_stream() -> None:
    upload = _CappedUpload(total=10 * 1024 * 1024, chunk=1024 * 1024)
    with pytest.raises(UnreadableDossier, match="tamanho"):
        asyncio.run(_read_within_limit(cast(UploadFile, upload), max_bytes=1024))
    # One chunk is enough to pass a 1 KiB limit; the other nine are never read.
    assert upload.served <= 2 * 1024 * 1024


def _desk(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: Any,
) -> tuple[Any, ScriptedStore, MemoryHistory]:
    monkeypatch.setattr("orbe.api.app.prepare_database", lambda _engine: None)
    configured = settings(**overrides)
    store = ScriptedStore()
    history = MemoryHistory()
    application = build_app(
        settings=configured,
        indexer=DossierIndexer(store, history, allow_key, configured),
        reader=DossierReader(store, ScriptedChain(), history, allow_key, configured),
    )
    return application, store, history


def test_upload_over_limit_is_rejected_before_indexing(monkeypatch: pytest.MonkeyPatch) -> None:
    application, store, _history = _desk(monkeypatch, document_max_bytes=4)
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("grande.txt", b"abcdefghij", "text/plain")},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "O arquivo excede o tamanho permitido."
    assert store.added == []
    assert store.add_keys == []


def test_health_stays_responsive_while_a_document_indexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, _store, _history = _desk(monkeypatch)
    started = threading.Event()
    release = threading.Event()

    class BlockingIndexer:
        def index(self, filename: str, content: bytes) -> IndexedFile:
            started.set()
            if not release.wait(timeout=5):
                raise AssertionError("o teste não liberou a indexação")
            return IndexedFile(id=uuid4(), filename=filename, chunk_count=1, duplicate=False)

    application.state.indexer = BlockingIndexer()
    with TestClient(application) as client, ThreadPoolExecutor(max_workers=1) as pool:
        upload = pool.submit(
            lambda: client.post(
                "/api/v1/documents",
                files={"file": ("grande.txt", b"conteudo", "text/plain")},
            )
        )
        assert started.wait(timeout=5)
        # The index is blocked on a worker thread. The event loop must still answer.
        begin = time.perf_counter()
        live = client.get("/health/live")
        elapsed = time.perf_counter() - begin
        assert live.status_code == 200
        assert live.json()["status"] == "live"
        assert elapsed < 2.0
        release.set()
        assert upload.result(timeout=5).status_code == 201
