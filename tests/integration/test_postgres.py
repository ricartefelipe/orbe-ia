"""Reading desk against PostgreSQL and pgvector."""

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from orbe.api.app import build_app
from orbe.application.chain import UNGROUNDED_ANSWER, LangChainAnswer
from orbe.application.reading import DossierIndexer, DossierReader
from orbe.infrastructure.history import SqlReadingHistory
from orbe.infrastructure.vector_store import PgExcerptStore
from tests.support import allow_key, settings


class MarkerEmbeddings(Embeddings):
    """Vectors that match only text containing the word prazo."""

    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        value = 1.0 if "prazo" in text.casefold() else -1.0
        return [value] * self._dimensions


@pytest.fixture
def desk() -> Iterator[tuple[TestClient, Engine, str]]:
    collection = "it_" + uuid.uuid4().hex[:16]
    configured = settings(
        database_url=os.environ["DATABASE_URL"],
        collection_name=collection,
        embedding_dimensions=8,
        openai_api_key="",
    )
    engine = create_engine(configured.database_url)
    store = PgExcerptStore(configured, MarkerEmbeddings(), engine)
    history = SqlReadingHistory(engine)
    chain = LangChainAnswer(FakeListChatModel(responses=["O prazo aparece no dossiê."]))
    indexer = DossierIndexer(store, history, allow_key, configured)
    reader = DossierReader(store, chain, history, allow_key, configured)
    application = build_app(
        settings=configured,
        indexer=indexer,
        reader=reader,
        engine=engine,
    )
    application.state.history = history
    with TestClient(application) as client:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM asked_citations"))
            connection.execute(text("DELETE FROM asked_questions"))
            connection.execute(text("DELETE FROM dossier_files"))
        yield client, engine, collection
    engine.dispose()


@pytest.mark.integration
def test_close_excerpt_is_cited(desk: tuple[TestClient, Engine, str]) -> None:
    client, _engine, _collection = desk
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("prazo.txt", "O prazo é de 30 dias.\n".encode(), "text/plain")},
    )
    assert uploaded.status_code == 201
    asked = client.post("/api/v1/queries", json={"question": "qual o prazo?"})
    assert asked.status_code == 200
    body = asked.json()
    assert body["grounded"] is True
    assert body["answer"] == "O prazo aparece no dossiê."
    assert body["citations"]
    assert "prazo" in body["citations"][0]["content"]
    assert body["citations"][0]["distance"] <= 0.5


@pytest.mark.integration
def test_distant_excerpt_does_not_call_the_model(
    desk: tuple[TestClient, Engine, str],
) -> None:
    client, _engine, _collection = desk
    client.post(
        "/api/v1/documents",
        files={"file": ("prazo.txt", "O prazo é de 30 dias.\n".encode(), "text/plain")},
    )
    asked = client.post("/api/v1/queries", json={"question": "qual a cor do selo?"})
    body = asked.json()
    assert body["grounded"] is False
    assert body["answer"] == UNGROUNDED_ANSWER
    assert body["citations"] == []


@pytest.mark.integration
def test_contradiction_returns_both_excerpts() -> None:
    collection = "it_" + uuid.uuid4().hex[:16]
    configured = settings(
        database_url=os.environ["DATABASE_URL"],
        collection_name=collection,
        embedding_dimensions=8,
        chunk_size=24,
        chunk_overlap=0,
    )
    engine = create_engine(configured.database_url)
    store = PgExcerptStore(configured, MarkerEmbeddings(), engine)
    history = SqlReadingHistory(engine)
    chain = LangChainAnswer(FakeListChatModel(responses=["Os dois prazos aparecem no arquivo."]))
    application = build_app(
        settings=configured,
        indexer=DossierIndexer(store, history, allow_key, configured),
        reader=DossierReader(store, chain, history, allow_key, configured),
        engine=engine,
    )
    payload = "O prazo é de 30 dias.\n\nO prazo é de 10 dias.\n"
    with TestClient(application) as client:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM asked_citations"))
            connection.execute(text("DELETE FROM asked_questions"))
            connection.execute(text("DELETE FROM dossier_files"))
        uploaded = client.post(
            "/api/v1/documents",
            files={"file": ("prazo.txt", payload.encode(), "text/plain")},
        )
        assert uploaded.json()["chunk_count"] == 2
        asked = client.post("/api/v1/queries", json={"question": "qual o prazo?"})
        contents = [item["content"] for item in asked.json()["citations"]]
        assert any("30" in item for item in contents)
        assert any("10" in item for item in contents)
        assert asked.json()["answer"] == "Os dois prazos aparecem no arquivo."
    engine.dispose()


@pytest.mark.integration
def test_same_bytes_are_not_embedded_twice(desk: tuple[TestClient, Engine, str]) -> None:
    client, engine, collection = desk
    content = "O prazo é de 30 dias.\n".encode()
    first = client.post("/api/v1/documents", files={"file": ("prazo.txt", content, "text/plain")})
    second = client.post("/api/v1/documents", files={"file": ("copia.txt", content, "text/plain")})
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    with engine.connect() as connection:
        count: int = connection.execute(
            text(
                "SELECT count(*) FROM langchain_pg_embedding AS embedding "
                "JOIN langchain_pg_collection AS collection "
                "ON embedding.collection_id = collection.uuid "
                "WHERE collection.name = :name"
            ),
            {"name": collection},
        ).scalar_one()
    assert count == 1
