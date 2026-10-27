"""HTTP desk."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from orbe.api.app import build_app
from orbe.application.reading import DossierIndexer, DossierReader
from orbe.domain.errors import ModelCallFailed
from tests.support import MemoryHistory, ScriptedChain, ScriptedStore, allow_key, settings


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, ScriptedStore, ScriptedChain]]:
    monkeypatch.setattr("orbe.api.app.prepare_database", lambda _engine: None)
    store = ScriptedStore()
    history = MemoryHistory()
    chain = ScriptedChain("O prazo é de 30 dias.")
    configured = settings()
    indexer = DossierIndexer(store, history, allow_key, configured)
    reader = DossierReader(store, chain, history, allow_key, configured)
    application = build_app(settings=configured, indexer=indexer, reader=reader)
    with TestClient(application) as test_client:
        yield test_client, store, chain


def test_live_page_and_favicon(client: tuple[TestClient, ScriptedStore, ScriptedChain]) -> None:
    test_client, _store, _chain = client
    live = test_client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "live"
    page = test_client.get("/")
    assert page.status_code == 200
    assert "Escolher arquivo" in page.text
    assert "unsafe-inline" not in page.headers["content-security-policy"]
    assert test_client.get("/favicon.ico").status_code == 204
    script = test_client.get("/assets/app.js")
    assert script.status_code == 200
    assert "innerHTML" not in script.text
    assert "insertAdjacentHTML" not in script.text
    schema = test_client.get("/openapi.json").json()
    assert "/favicon.ico" not in schema["paths"]
    assert "/" not in schema["paths"]


def test_request_id_is_returned_and_echoed(
    client: tuple[TestClient, ScriptedStore, ScriptedChain],
) -> None:
    test_client, _store, _chain = client
    generated = test_client.get("/health/live")
    assert generated.headers["x-request-id"]
    echoed = test_client.get("/health/live", headers={"X-Request-ID": "pedido-123"})
    assert echoed.headers["x-request-id"] == "pedido-123"


def test_ready_without_database_is_unavailable(
    client: tuple[TestClient, ScriptedStore, ScriptedChain],
) -> None:
    test_client, _store, _chain = client
    ready = test_client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.headers["content-type"].startswith("application/problem+json")
    assert "input" not in ready.json()


def test_upload_and_question(client: tuple[TestClient, ScriptedStore, ScriptedChain]) -> None:
    test_client, store, _chain = client
    uploaded = test_client.post(
        "/api/v1/documents",
        files={"file": ("prazo.txt", b"O prazo e de 30 dias.\n", "text/plain")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["duplicate"] is False
    assert store.added
    store.matches = [(store.added[0], 0.1)]
    asked = test_client.post("/api/v1/queries", json={"question": "qual o prazo?"})
    assert asked.status_code == 200
    body = asked.json()
    assert body["grounded"] is True
    assert body["citations"][0]["filename"] == "prazo.txt"
    assert "prazo" in body["citations"][0]["content"]


def test_list_documents(client: tuple[TestClient, ScriptedStore, ScriptedChain]) -> None:
    test_client, _store, _chain = client
    assert test_client.get("/api/v1/documents").json() == []
    test_client.post(
        "/api/v1/documents",
        files={"file": ("prazo.txt", b"O prazo e de 30 dias.\n", "text/plain")},
    )
    listed = test_client.get("/api/v1/documents")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["filename"] == "prazo.txt"
    assert body[0]["chunk_count"] >= 1
    assert "id" in body[0]


def test_delete_document(client: tuple[TestClient, ScriptedStore, ScriptedChain]) -> None:
    test_client, store, _chain = client
    uploaded = test_client.post(
        "/api/v1/documents",
        files={"file": ("prazo.txt", b"O prazo e de 30 dias.\n", "text/plain")},
    )
    document_id = uploaded.json()["id"]
    deleted = test_client.delete(f"/api/v1/documents/{document_id}")
    assert deleted.status_code == 204
    assert store.removed
    missing = test_client.delete(f"/api/v1/documents/{uuid4()}")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert "input" not in missing.json()
    malformed = test_client.delete("/api/v1/documents/nao-e-uuid")
    assert malformed.status_code == 422


def test_missing_key_and_unreadable_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("orbe.api.app.prepare_database", lambda _engine: None)

    def refuse() -> None:
        from orbe.domain.errors import MissingOpenAIKey

        raise MissingOpenAIKey("A chave da OpenAI não está configurada.")

    configured = settings()
    store = ScriptedStore()
    history = MemoryHistory()
    application = build_app(
        settings=configured,
        indexer=DossierIndexer(store, history, refuse, configured),
        reader=DossierReader(store, ScriptedChain(), history, refuse, configured),
    )
    with TestClient(application) as test_client:
        uploaded = test_client.post(
            "/api/v1/documents",
            files={"file": ("prazo.txt", b"O prazo e de 30 dias.\n", "text/plain")},
        )
        assert uploaded.status_code == 503
        assert uploaded.json()["detail"] == "A chave da OpenAI não está configurada."
        assert uploaded.headers["content-type"].startswith("application/problem+json")
        empty = test_client.post(
            "/api/v1/documents",
            files={"file": ("prazo.txt", b"", "text/plain")},
        )
        assert empty.status_code == 422
        broken = test_client.post("/api/v1/queries", json={})
        assert broken.status_code == 422
        assert "input" not in broken.json()


def test_model_and_unexpected_failures_hide_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("orbe.api.app.prepare_database", lambda _engine: None)
    configured = settings()
    store = ScriptedStore()
    history = MemoryHistory()

    class Exploding:
        def index(self, filename: str, content: bytes) -> None:
            raise RuntimeError("senha-do-banco")

        def ask(self, question: str) -> None:
            raise ModelCallFailed("O modelo não concluiu a resposta.")

    application = build_app(
        settings=configured,
        indexer=DossierIndexer(store, history, allow_key, configured),
        reader=DossierReader(store, ScriptedChain(), history, allow_key, configured),
    )
    application.state.indexer = Exploding()
    application.state.reader = Exploding()
    with TestClient(application, raise_server_exceptions=False) as test_client:
        uploaded = test_client.post(
            "/api/v1/documents",
            files={"file": ("prazo.txt", b"texto\n", "text/plain")},
        )
        assert uploaded.status_code == 500
        assert uploaded.json()["detail"] == "A mesa não conseguiu concluir a operação."
        assert "senha-do-banco" not in uploaded.text
        asked = test_client.post("/api/v1/queries", json={"question": "qual o prazo?"})
        assert asked.status_code == 502
        assert "concluiu" in asked.json()["detail"]
