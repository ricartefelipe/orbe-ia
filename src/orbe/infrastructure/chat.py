"""OpenAI chat wrapped by the LangChain answer chain."""

from collections.abc import Sequence

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from orbe.application.chain import LangChainAnswer
from orbe.config.settings import Settings
from orbe.domain.errors import ModelCallFailed, OrbeError
from orbe.domain.models import Chunk
from orbe.infrastructure.keys import require_openai_key
from orbe.logging import log_failure


class OpenAIAnswerChain:
    """Build a chat model on demand and answer from the supplied excerpts."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def answer(self, question: str, chunks: Sequence[Chunk]) -> str:
        require_openai_key(self._settings)
        try:
            chat = ChatOpenAI(
                model=self._settings.openai_chat_model,
                api_key=SecretStr(self._settings.openai_api_key),
                timeout=self._settings.openai_timeout,
                max_retries=1,
            )
            return LangChainAnswer(chat).answer(question, chunks)
        except OrbeError:
            raise
        except Exception as exc:
            log_failure(type(exc).__name__)
            raise ModelCallFailed("O modelo não concluiu a resposta.") from None
