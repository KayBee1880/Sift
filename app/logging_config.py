"""Structured (JSON) logging setup for the API.

Real, standard-library-only implementation, no new dependency (e.g.
python-json-logger) — the same minimal-dependency instinct already applied
elsewhere in this project (raw httpx over the groq SDK, bcrypt/PyJWT
directly over a heavier auth framework). Output goes to stdout, which
Render's free tier already captures and shows in its Logs tab — no new
logging service or infrastructure needed.

Built in response to a real, observed gap, not speculatively: the
2026-09-18 out-of-memory incident on the live deployment had zero
application-level diagnostic signal, only Render's platform-level
"exceeded its memory limit" notification. This closes that specific gap.
"""

import json
import logging

# The standard attributes every LogRecord carries regardless of what's logged
# — anything else found on a record came from a logger.info(..., extra={...})
# call and should be surfaced as its own JSON field, not skipped.
_RESERVED_LOG_RECORD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED_LOG_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # default=str: extra fields are whatever a caller passes (floats, bools,
        # ints so far), but this guards against a future extra field that isn't
        # natively JSON-serializable rather than letting logging itself crash.
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
