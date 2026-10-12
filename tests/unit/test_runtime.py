"""Process entry."""

import pytest

from orbe.config.settings import get_settings


def test_module_starts_uvicorn_without_access_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def run(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", run)
    get_settings.cache_clear()
    from orbe.__main__ import main

    main()
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["access_log"] is False
    assert kwargs["host"] == "127.0.0.1"
    get_settings.cache_clear()
