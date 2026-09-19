import json
import logging
import sys

from app.logging_config import JSONFormatter


def _make_record(**kwargs) -> logging.LogRecord:
    defaults = {
        "name": "sift.test",
        "level": logging.INFO,
        "pathname": __file__,
        "lineno": 1,
        "msg": "a message",
        "args": (),
        "exc_info": None,
    }
    defaults.update(kwargs)
    return logging.LogRecord(**defaults)


def test_format_produces_valid_json_with_core_fields():
    record = _make_record(msg="hello world")
    parsed = json.loads(JSONFormatter().format(record))

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "sift.test"
    assert parsed["message"] == "hello world"
    assert "timestamp" in parsed


def test_format_includes_extra_fields_passed_via_logging_call():
    logger = logging.getLogger("sift.test.extra")
    record = logger.makeRecord(
        "sift.test.extra",
        logging.INFO,
        __file__,
        1,
        "query handled",
        (),
        None,
        extra={"username": "admin", "abstained": False, "citation_count": 2},
    )
    parsed = json.loads(JSONFormatter().format(record))

    assert parsed["username"] == "admin"
    assert parsed["abstained"] is False
    assert parsed["citation_count"] == 2
    # Not silently dropped into the message string, each is its own real field.
    assert parsed["message"] == "query handled"


def test_format_does_not_leak_internal_logrecord_attributes_as_extra_fields():
    # A record with no real "extra" fields should produce exactly the core
    # keys, not every standard LogRecord attribute (lineno, pathname,
    # thread, etc.) leaking through as if they were meaningful extras.
    record = _make_record(msg="plain message")
    parsed = json.loads(JSONFormatter().format(record))

    assert set(parsed.keys()) == {"timestamp", "level", "logger", "message"}


def test_format_includes_exception_info_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        record = _make_record(msg="failed", exc_info=sys.exc_info())

    parsed = json.loads(JSONFormatter().format(record))
    assert "exception" in parsed
    assert "ValueError: boom" in parsed["exception"]
