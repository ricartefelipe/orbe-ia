"""Process configuration. Keys come only from the environment."""

import re
from enum import StrEnum
from functools import lru_cache
from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError

_WILDCARD_HOSTS = {"0.0.0.0", "::", "[::]"}  # noqa: S104
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
_POSTGRES_DRIVER = "postgresql+psycopg"
_COLLECTION_NAME = r"^[a-z][a-z0-9_]{0,62}$"


class AppEnvironment(StrEnum):
    """Deployment environments with different configuration constraints."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Process configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_env: AppEnvironment = AppEnvironment.LOCAL
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    database_url: str = Field(repr=False)
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_timeout: float = Field(default=30, gt=0, le=120)
    db_connect_timeout: int = Field(default=5, ge=1, le=60)
    document_max_bytes: int = Field(default=10_485_760, ge=1, le=52_428_800)
    index_max_concurrency: int = Field(default=2, ge=1, le=16)
    chunk_size: int = Field(default=1000, ge=1, le=8000)
    chunk_overlap: int = Field(default=200, ge=0, le=7999)
    openai_api_key: str = Field(default="", repr=False)
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout: float = Field(default=30, gt=0, le=120)
    openai_max_retries: int = Field(default=2, ge=0, le=5)
    embedding_dimensions: int = Field(default=1536, ge=1, le=3072)
    langsmith_api_key: str = Field(default="", repr=False)
    langsmith_project: str = "orbe"
    collection_name: str = "orbe_dossiers"
    query_max_distance: float = Field(default=0.5, ge=0, le=2)
    query_match_limit: int = Field(default=5, ge=1, le=20)
    query_max_chars: int = Field(default=2000, ge=1, le=8000)

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("app_host", mode="before")
    @classmethod
    def normalize_app_host(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                raise ValueError("APP_HOST must not be empty")
            return stripped
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized not in _LOG_LEVELS:
                raise ValueError("LOG_LEVEL must be CRITICAL, ERROR, WARNING, INFO, or DEBUG")
            return normalized
        return value

    @field_validator("openai_api_key", "langsmith_api_key", mode="before")
    @classmethod
    def normalize_secret(cls, value: object) -> object:
        if isinstance(value, str):
            if any(character in value for character in "\r\n"):
                raise ValueError("secret is invalid")
            return value.strip()
        return value

    @field_validator("openai_chat_model", "openai_embedding_model", mode="before")
    @classmethod
    def normalize_model_name(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "" or any(character.isspace() for character in stripped):
                raise ValueError("model name must be a single token")
            return stripped
        return value

    @field_validator("langsmith_project", "collection_name", mode="before")
    @classmethod
    def normalize_token(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                raise ValueError("name must not be empty")
            return stripped
        return value

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, value: str) -> str:
        if re.fullmatch(_COLLECTION_NAME, value) is None:
            raise ValueError("COLLECTION_NAME must match ^[a-z][a-z0-9_]{0,62}$")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if any(character in value for character in "\r\n"):
            raise ValueError("DATABASE_URL is not a valid database URL")
        try:
            url = make_url(value)
        except ArgumentError as exc:
            raise ValueError("DATABASE_URL is not a valid database URL") from exc
        if url.drivername != _POSTGRES_DRIVER:
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        if not url.database:
            raise ValueError("DATABASE_URL must include a database name")
        return value

    @model_validator(mode="after")
    def validate_chunk_geometry(self) -> Self:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    @model_validator(mode="after")
    def validate_production_constraints(self) -> Self:
        if self.app_env is not AppEnvironment.PRODUCTION:
            return self
        url = make_url(self.database_url)
        if not url.host:
            raise ValueError("production DATABASE_URL requires a host")
        password = url.password
        if password is None or password.strip() == "":
            raise ValueError("production DATABASE_URL requires a password")
        if self.app_host in _WILDCARD_HOSTS:
            raise ValueError("production APP_HOST must not listen on all interfaces")
        parsed = urlsplit(f"http://{self.app_host}")
        if parsed.hostname in _WILDCARD_HOSTS:
            raise ValueError("production APP_HOST must not listen on all interfaces")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings, loaded once per process."""

    return Settings()
