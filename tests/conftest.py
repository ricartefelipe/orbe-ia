"""Shared fixtures. The database URL is only a default; tests pass settings explicitly."""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://orbe:orbe@127.0.0.1:5432/orbe_test",
)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LANGSMITH_API_KEY", "")
