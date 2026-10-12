"""Failure logs keep the error type only."""

import logging
from io import StringIO

from orbe.logging import JsonFormatter, log_failure


def test_failure_log_records_only_the_type() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("orbe")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    try:
        log_failure("RuntimeError")
    finally:
        logger.removeHandler(handler)
    rendered = stream.getvalue()
    assert "RuntimeError" in rendered
    assert "senha-do-banco" not in rendered
    assert "operation_failed" in rendered
