"""JSON logs. Failure records keep the error type and drop the exception text."""

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """One JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        error_type = getattr(record, "error_type", None)
        if isinstance(error_type, str):
            payload["error_type"] = error_type
        return json.dumps(payload, ensure_ascii=False)


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
