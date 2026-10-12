"""OpenAI embeddings created only when an operation needs them."""

from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from orbe.config.settings import Settings
from orbe.domain.errors import ModelCallFailed, OrbeError
from orbe.infrastructure.keys import require_openai_key
from orbe.logging import log_failure


class OpenAIEmbeddingAdapter(Embeddings):
    """LangChain embeddings backed by the OpenAI API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: OpenAIEmbeddings | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._embeddings().embed_documents(texts)
        except OrbeError:
            raise
        except Exception as exc:
            log_failure(type(exc).__name__)
            raise ModelCallFailed("O modelo não concluiu a resposta.") from None

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._embeddings().embed_query(text)
        except OrbeError:
            raise
        except Exception as exc:
            log_failure(type(exc).__name__)
            raise ModelCallFailed("O modelo não concluiu a resposta.") from None

    def _embeddings(self) -> OpenAIEmbeddings:
        require_openai_key(self._settings)
        if self._client is None:
            self._client = OpenAIEmbeddings(
                model=self._settings.openai_embedding_model,
                openai_api_key=SecretStr(self._settings.openai_api_key),
                dimensions=self._settings.embedding_dimensions,
                request_timeout=self._settings.openai_timeout,
                max_retries=1,
            )
        return self._client

    def client(self) -> Any:
        """Return the underlying client after the key check."""

        return self._embeddings()
