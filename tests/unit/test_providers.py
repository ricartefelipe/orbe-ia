"""OpenAI adapters stay unbuilt until a key exists."""

import pytest
from pydantic import SecretStr

from orbe.domain.errors import MissingOpenAIKey, ModelCallFailed
from orbe.domain.models import Chunk
from orbe.infrastructure.chat import OpenAIAnswerChain
from orbe.infrastructure.embeddings import OpenAIEmbeddingAdapter
from orbe.infrastructure.keys import require_openai_key
from tests.support import settings


def test_missing_key_does_not_build_a_client() -> None:
    configured = settings()
    with pytest.raises(MissingOpenAIKey, match="não está configurada"):
        require_openai_key(configured)
    with pytest.raises(MissingOpenAIKey, match="não está configurada"):
        OpenAIEmbeddingAdapter(configured).embed_query("prazo")
    with pytest.raises(MissingOpenAIKey, match="não está configurada"):
        OpenAIAnswerChain(configured).answer("qual o prazo?", [Chunk("a.txt", 0, "prazo")])


def test_embedding_client_keeps_the_key_secret() -> None:
    adapter = OpenAIEmbeddingAdapter(settings(openai_api_key="sk-test"))
    client = adapter.client()
    secret = client.openai_api_key
    assert isinstance(secret, SecretStr)
    assert secret.get_secret_value() == "sk-test"


def test_chat_failure_hides_the_exception_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("senha-do-banco")

    monkeypatch.setattr("orbe.infrastructure.chat.ChatOpenAI", Boom)
    with pytest.raises(ModelCallFailed, match="não concluiu") as caught:
        OpenAIAnswerChain(settings(openai_api_key="sk-test")).answer(
            "qual o prazo?",
            [Chunk("a.txt", 0, "prazo")],
        )
    assert "senha-do-banco" not in str(caught.value)
