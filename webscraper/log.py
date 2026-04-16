"""Structured JSON-line logger with cookie/credential redaction."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = ("cookie", "set-cookie", "authorization")
_SENSITIVE_PREFIX = ("x-auth-",)


class RedactionFilter(logging.Filter):
    """Strip cookie-like and auth-like values from log records (top-level and nested dicts)."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__.keys()):
            record.__dict__[key] = self._scrub(key, record.__dict__[key])
        return True

    def _scrub(self, key: str, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._scrub(k, v) for k, v in value.items()}
        if self._is_sensitive(key):
            return REDACTED
        return value

    @staticmethod
    def _is_sensitive(key: str) -> bool:
        k = key.lower()
        if k in _SENSITIVE_KEYS:
            return True
        return any(k.startswith(p) for p in _SENSITIVE_PREFIX)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        standard = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
        }
        for k, v in record.__dict__.items():
            if k in standard:
                continue
            payload[k] = v
        return json.dumps(payload, default=str)


def configure(*, level: str = "INFO", stream: Any = None) -> None:
    """Install the JSON formatter and redaction filter on the root logger."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"webscraper.{name}")
