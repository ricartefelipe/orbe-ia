"""PostgreSQL is local and named orbe or orbe_test."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "db"}
_ALLOWED_DATABASES = {"orbe", "orbe_test"}


@pytest.fixture(scope="session", autouse=True)
def prepare_local_postgres() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    host = url.host or ""
    if host not in _ALLOWED_HOSTS or url.database not in _ALLOWED_DATABASES:
        pytest.fail("A integração só roda em PostgreSQL local, no banco orbe ou orbe_test.")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text("DROP TABLE IF EXISTS asked_citations"))
        connection.execute(text("DROP TABLE IF EXISTS asked_questions"))
        connection.execute(text("DROP TABLE IF EXISTS dossier_files"))
        connection.execute(text("DROP TABLE IF EXISTS langchain_pg_embedding"))
        connection.execute(text("DROP TABLE IF EXISTS langchain_pg_collection"))
    engine.dispose()
