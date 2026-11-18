"""Structured JSON logs that cannot carry client text or phone numbers.

Rules enforced here (and tested):
- fields that normally hold message content are replaced by ``[redacted]``;
- phone-number-like sequences and e-mail addresses are masked in every string;
- the text of an exception is never logged, only its type.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime
from typing import Any, TextIO

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

# Names of fields that hold (or may hold) client text, never to be logged.
FORBIDDEN_KEYS = frozenset(
    {
        "text",
        "body",
        "content",
        "caption",
        "payload",
        "message",
        "message_text",
        "reply_text",
        "summary",
        "display_name",
        "filename",
    }
)

_PHONE_RE = re.compile(r"(?<![\w])\+?\d(?:[\d\s().-]{6,}\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    | {"message", "asctime", "taskName"}
)


def new_correlation_id() -> str:
    value = uuid.uuid4().hex
    _correlation_id.set(value)
    return value


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def mask_text(value: str) -> str:
    """Mask phone-like numbers and e-mail addresses in a free-form string."""
    return _EMAIL_RE.sub("[email]", _PHONE_RE.sub("[phone]", value))


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {str(k): _clean_field(str(k), v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_clean(v) for v in value]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return mask_text(str(value))


def _clean_field(key: str, value: Any) -> Any:
    if key.lower() in FORBIDDEN_KEYS:
        return "[redacted]"
    return _clean(value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": mask_text(record.getMessage()),
            "correlation_id": get_correlation_id(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                entry[key] = _clean_field(key, value)
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc_type"] = record.exc_info[0].__name__
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
