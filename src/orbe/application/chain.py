"""LangChain answer chain. Citations are not parsed from this text."""

from collections.abc import Sequence
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from orbe.domain.errors import ModelCallFailed
from orbe.domain.models import Chunk

SYSTEM_PROMPT = (
    "Você responde em português somente com base nas fontes numeradas. "
    "Se duas fontes se contradizem, mostre as duas e não escolha um vencedor. "
    "Se as fontes não contiverem a resposta, diga que o dossiê não cobre a pergunta. "
    "Não invente fatos. Mencione o nome do arquivo."
)

UNGROUNDED_ANSWER = "O dossiê não cobre essa pergunta."


def format_sources(chunks: Sequence[Chunk]) -> str:
    """Number the excerpts the chain is allowed to use."""

    blocks = [
        f"[{index}] {chunk.filename} (posição {chunk.position})\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    ]
    return "\n\n".join(blocks)


def build_prompt() -> ChatPromptTemplate:
    """Prompt that keeps the model inside the numbered excerpts."""

    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "Pergunta: {question}\n\nFontes:\n{sources}"),
        ]
    )


class LangChainAnswer:
    """LCEL chain: prompt, chat model, and plain-text parser."""

    def __init__(self, chat: Any) -> None:
        self._runnable: Any = build_prompt() | chat | StrOutputParser()

    def answer(self, question: str, chunks: Sequence[Chunk]) -> str:
        text = self._runnable.invoke({"question": question, "sources": format_sources(chunks)})
        if not isinstance(text, str) or text.strip() == "":
            raise ModelCallFailed("O modelo devolveu uma resposta vazia.")
        return text.strip()
