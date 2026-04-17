"""Structured logger and redaction filter tests."""

import json
import logging

from webscraper.log import RedactionFilter, configure, get_logger


# [F-NONE]
def test_logger_emits_jsonl(capsys) -> None:  # type: ignore[no-untyped-def]
    configure(level="INFO")
    log = get_logger("t")
    log.info("hello", extra={"extra_k": "v"})
    captured = capsys.readouterr().err.strip().splitlines()
    record = json.loads(captured[-1])
    assert record["level"] == "INFO"
    assert record["event"] == "hello"
    assert record["extra_k"] == "v"
    assert "ts" in record


# [F-NONE]
def test_redaction_filter_strips_cookie_header() -> None:
    f = RedactionFilter()
    record = logging.makeLogRecord(
        {
            "msg": "req",
            "args": (),
            "Cookie": "session=secret",
            "headers": {"Cookie": "session=secret", "User-Agent": "ua"},
        }
    )
    assert f.filter(record) is True
    assert record.__dict__["Cookie"] == "[REDACTED]"
    assert record.__dict__["headers"]["Cookie"] == "[REDACTED]"
    assert record.__dict__["headers"]["User-Agent"] == "ua"


# [F-NONE]
def test_redaction_covers_authorization_and_auth_prefix() -> None:
    f = RedactionFilter()
    record = logging.makeLogRecord(
        {
            "msg": "req",
            "args": (),
            "Authorization": "Bearer abc",
            "X-Auth-Token": "xyz",
        }
    )
    f.filter(record)
    assert record.__dict__["Authorization"] == "[REDACTED]"
    assert record.__dict__["X-Auth-Token"] == "[REDACTED]"
