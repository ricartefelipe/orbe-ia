"""LangChain answer chain with a scripted chat model."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from orbe.application.chain import SYSTEM_PROMPT, LangChainAnswer, format_sources
from orbe.domain.errors import ModelCallFailed
from orbe.domain.models import Chunk


def test_chain_returns_the_model_text() -> None:
    chain = LangChainAnswer(FakeListChatModel(responses=["O prazo é de 30 dias."]))
    text = chain.answer("qual o prazo?", [Chunk("prazo.txt", 0, "O prazo é de 30 dias.")])
    assert text == "O prazo é de 30 dias."


def test_empty_model_text_fails() -> None:
    chain = LangChainAnswer(FakeListChatModel(responses=["   "]))
    with pytest.raises(ModelCallFailed, match="vazia"):
        chain.answer("qual o prazo?", [Chunk("prazo.txt", 0, "O prazo é de 30 dias.")])


def test_sources_keep_both_sides() -> None:
    rendered = format_sources(
        [
            Chunk("prazo.txt", 0, "O prazo é de 30 dias."),
            Chunk("prazo.txt", 24, "O prazo é de 10 dias."),
        ]
    )
    assert "O prazo é de 30 dias." in rendered
    assert "O prazo é de 10 dias." in rendered
    assert "prazo.txt" in rendered
    assert "contradizem" in SYSTEM_PROMPT
