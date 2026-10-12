"""Settings constraints."""

import pytest
from pydantic import ValidationError

from orbe.config.settings import Settings, get_settings
from tests.support import settings


def test_local_defaults_allow_an_empty_key() -> None:
    configured = settings()
    assert configured.openai_api_key == ""
    assert configured.openai_chat_model == "gpt-4o-mini"
    assert configured.openai_embedding_model == "text-embedding-3-small"
    assert configured.embedding_dimensions == 1536
    assert configured.query_max_distance == 0.5
    assert configured.collection_name == "orbe_dossiers"


def test_production_rejects_an_open_host_and_a_missing_password() -> None:
    with pytest.raises(ValidationError, match="password"):
        settings(
            app_env="production",
            database_url="postgresql+psycopg://orbe@127.0.0.1:5432/orbe",
        )
    with pytest.raises(ValidationError, match="host"):
        settings(
            app_env="production",
            database_url="postgresql+psycopg://orbe:orbe@/orbe",
        )
    with pytest.raises(ValidationError, match="all interfaces"):
        settings(
            app_env="production",
            app_host="0.0.0.0",
            database_url="postgresql+psycopg://orbe:orbe@127.0.0.1:5432/orbe",
        )


def test_collection_name_and_chunk_geometry_are_constrained() -> None:
    with pytest.raises(ValidationError, match="COLLECTION_NAME"):
        settings(collection_name="Orbe")
    with pytest.raises(ValidationError, match="CHUNK_OVERLAP"):
        settings(chunk_size=10, chunk_overlap=10)
    with pytest.raises(ValidationError, match="postgresql"):
        settings(database_url="sqlite:///tmp/orbe.db")


def test_get_settings_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://orbe:orbe@127.0.0.1:5432/orbe_test",
    )
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    loaded = get_settings()
    assert isinstance(loaded, Settings)
    get_settings.cache_clear()
