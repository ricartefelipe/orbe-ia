"""pgvector excerpts through LangChain PGVector."""

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy
from sqlalchemy.engine import Engine

from orbe.config.settings import Settings
from orbe.domain.errors import ModelCallFailed, OrbeError
from orbe.domain.models import Chunk
from orbe.logging import log_failure


class PgExcerptStore:
    """Adapter over PGVector. Scores are cosine distances."""

    def __init__(self, settings: Settings, embeddings: Embeddings, engine: Engine) -> None:
        self._collection = settings.collection_name
        self._vector: Any = PGVector(
            embeddings=embeddings,
            connection=engine,
            collection_name=settings.collection_name,
            distance_strategy=DistanceStrategy.COSINE,
            embedding_length=settings.embedding_dimensions,
            use_jsonb=True,
            create_extension=True,
            pre_delete_collection=False,
            async_mode=False,
        )

    def add(self, key: str, filename: str, chunks: Sequence[Chunk]) -> None:
        documents = [
            Document(
                page_content=chunk.content,
                metadata={"filename": filename, "position": chunk.position},
            )
            for chunk in chunks
        ]
        # Deterministic ids keyed on the content fingerprint. PGVector upserts on
        # conflicting ids, so re-indexing the same bytes after a crash replaces the
        # same rows instead of appending duplicate excerpts. The id row is a global
        # primary key, so the collection name scopes it to keep two collections that
        # hold the same bytes from overwriting each other.
        ids = [f"{self._collection}:{key}:{index}" for index in range(len(documents))]
        try:
            self._vector.add_documents(documents, ids=ids)
        except OrbeError:
            raise
        except Exception as exc:
            log_failure(type(exc).__name__)
            raise ModelCallFailed("O modelo não concluiu a resposta.") from None

    def remove(self, key: str, count: int) -> None:
        ids = [f"{self._collection}:{key}:{index}" for index in range(count)]
        if not ids:
            return
        try:
            self._vector.delete(ids=ids)
        except OrbeError:
            raise
        except Exception as exc:
            log_failure(type(exc).__name__)
            raise ModelCallFailed("O modelo não concluiu a resposta.") from None

    def search(self, question: str, limit: int) -> list[tuple[Chunk, float]]:
        try:
            pairs = self._vector.similarity_search_with_score(question, k=limit)
        except OrbeError:
            raise
        except Exception as exc:
            log_failure(type(exc).__name__)
            raise ModelCallFailed("O modelo não concluiu a resposta.") from None
        found: list[tuple[Chunk, float]] = []
        for document, score in pairs:
            metadata = document.metadata
            filename = metadata.get("filename", "")
            position = metadata.get("position", 0)
            if not isinstance(filename, str) or not isinstance(position, int):
                continue
            found.append(
                (
                    Chunk(filename=filename, position=position, content=document.page_content),
                    float(score),
                )
            )
        return found
