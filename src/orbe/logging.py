"""JSON logs. Failure records keep the error type and drop the exception text."""

import json
import logging
from contextvars import ContextVar
from typing import Any

_request_id: ContextVar[str] = ContextVar("orbe_request_id", default="")

_EXTRA_STR_FIELDS = ("error_type", "method", "path")


class JsonFormatter(logging.Formatter):
    """One JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = _request_id.get()
        if request_id:
            payload["request_id"] = request_id
        for field in _EXTRA_STR_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, str):
                payload[field] = value
        status = getattr(record, "status", None)
        if isinstance(status, int):
            payload["status"] = status
        return json.dumps(payload, ensure_ascii=False)


def set_request_id(value: str) -> None:
    """Bind the current request id so later log lines carry it."""

    _request_id.set(value)


def get_request_id() -> str:
    """Return the request id bound to the current context, or an empty string."""

    return _request_id.get()


def configure_logging(level: str) -> None:
    """Attach a JSON handler to the desk logger."""

    logger = logging.getLogger("orbe")
    logger.setLevel(level)
    if not any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)


def log_failure(error_type: str) -> None:
    """Record a failure without the exception message."""

    logging.getLogger("orbe").error("operation_failed", extra={"error_type": error_type})


def log_request(method: str, path: str, status: int) -> None:
    """Record one finished HTTP request. The current request id is attached."""

    logging.getLogger("orbe").info(
        "request", extra={"method": method, "path": path, "status": status}
    )
