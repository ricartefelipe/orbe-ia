"""Enable LangSmith only when a key is present. The key is never logged."""

import os

from orbe.config.settings import Settings


def configure_tracing(settings: Settings) -> None:
    """Turn tracing on for a configured key and off otherwise."""

    key = settings.langsmith_api_key.strip()
    if key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project or "orbe"
        return
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ.pop("LANGSMITH_API_KEY", None)
