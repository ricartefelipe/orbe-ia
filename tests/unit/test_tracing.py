"""LangSmith is enabled only when a key is present."""

import os

import pytest

from orbe.infrastructure.tracing import configure_tracing
from tests.support import settings


def test_tracing_turns_on_with_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    configure_tracing(settings(langsmith_api_key="ls-test", langsmith_project="mesa"))
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-test"
    assert os.environ["LANGSMITH_PROJECT"] == "mesa"
    configure_tracing(settings())
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert "LANGSMITH_API_KEY" not in os.environ


def test_tracing_import_order() -> None:
    assert os.environ.get("LANGSMITH_TRACING") in {None, "true", "false"}
