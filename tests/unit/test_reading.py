"""Reading use cases."""

import pytest

from orbe.application.chain import UNGROUNDED_ANSWER
from orbe.application.reading import DossierIndexer, DossierReader
from orbe.domain.errors import InvalidQuestion, MissingOpenAIKey, UnreadableDossier
from orbe.domain.models import Chunk
from tests.support import MemoryHistory, ScriptedChain, ScriptedStore, allow_key, settings


def _indexer(store: ScriptedStore, history: MemoryHistory) -> DossierIndexer:
    return DossierIndexer(store, history, allow_key, settings())


def test_upload_rules_run_before_the_key() -> None:
    store = ScriptedStore()
    history = MemoryHistory()

    def refuse() -> None:
        raise MissingOpenAIKey("A chave da OpenAI não está configurada.")

    indexer = DossierIndexer(store, history, refuse, settings())
    with pytest.raises(UnreadableDossier, match="inválido"):
        indexer.index("../segredo.txt", b"texto")
    with pytest.raises(UnreadableDossier, match="vazio"):
        indexer.index("notas.txt", b"")
    with pytest.raises(MissingOpenAIKey, match="não está configurada"):
        indexer.index("notas.txt", b"prazo")
    assert store.added == []


def test_rejected_names() -> None:
    indexer = _indexer(ScriptedStore(), MemoryHistory())
    for name in ("", ".", "..", "a/b.txt", "a\\b.txt", "a\x00.txt", "n" * 256 + ".txt"):
        with pytest.raises(UnreadableDossier, match="inválido"):
            indexer.index(name, b"texto")
    with pytest.raises(UnreadableDossier, match="não é aceito"):
        indexer.index("notas.docx", b"texto")


def test_duplicate_hash_skips_embedding() -> None:
    store = ScriptedStore()
    history = MemoryHistory()
    indexer = _indexer(store, history)
    first = indexer.index("prazo.txt", b"O prazo e de 30 dias.\n")
    second = indexer.index("copia.txt", b"O prazo e de 30 dias.\n")
    assert first.duplicate is False
    assert second.duplicate is True
    assert second.id == first.id
    assert len(store.added) == 1


def test_far_excerpt_does_not_call_the_chain() -> None:
    store = ScriptedStore()
    store.matches = [(Chunk("prazo.txt", 0, "O prazo e de 30 dias."), 1.2)]
    chain = ScriptedChain("nao deveria")
    reader = DossierReader(store, chain, MemoryHistory(), allow_key, settings())
    asked = reader.ask("qual a cor do selo?")
    assert asked.grounded is False
    assert asked.answer == UNGROUNDED_ANSWER
    assert asked.citations == ()
    assert chain.calls == 0


def test_close_excerpts_keep_both_sides_of_a_contradiction() -> None:
    store = ScriptedStore()
    store.matches = [
        (Chunk("prazo.txt", 0, "O prazo é de 30 dias."), 0.1),
        (Chunk("prazo.txt", 24, "O prazo é de 10 dias."), 0.2),
    ]
    chain = ScriptedChain("Os dois prazos aparecem.")
    history = MemoryHistory()
    reader = DossierReader(store, chain, history, allow_key, settings())
    asked = reader.ask("  qual o prazo?  ")
    assert asked.grounded is True
    assert asked.answer == "Os dois prazos aparecem."
    assert [item.content for item in asked.citations] == [
        "O prazo é de 30 dias.",
        "O prazo é de 10 dias.",
    ]
    assert history.questions[0].id == asked.id
    assert chain.calls == 1


def test_question_limits() -> None:
    reader = DossierReader(ScriptedStore(), ScriptedChain(), MemoryHistory(), allow_key, settings())
    with pytest.raises(InvalidQuestion, match="vazia"):
        reader.ask("   ")
    with pytest.raises(InvalidQuestion, match="tamanho"):
        reader.ask("a" * 2001)


def test_oversized_file_uses_the_configured_limit() -> None:
    indexer = DossierIndexer(
        ScriptedStore(),
        MemoryHistory(),
        allow_key,
        settings(document_max_bytes=4),
    )
    with pytest.raises(UnreadableDossier, match="tamanho"):
        indexer.index("notas.txt", b"abcde")
