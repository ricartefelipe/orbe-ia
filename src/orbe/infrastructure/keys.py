"""Refuse an operation that needs the OpenAI key when it is absent."""

from orbe.config.settings import Settings
from orbe.domain.errors import MissingOpenAIKey


def require_openai_key(settings: Settings) -> None:
    """Raise when this process has no OpenAI key."""

    if settings.openai_api_key.strip() == "":
        raise MissingOpenAIKey("A chave da OpenAI não está configurada.")
