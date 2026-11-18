import io
import json
import logging

import pytest

from vgs.observability import configure_logging, new_correlation_id, set_correlation_id
from vgs.observability.logging import mask_text


def capture() -> io.StringIO:
    stream = io.StringIO()
    configure_logging("DEBUG", stream)
    return stream


def last_entry(stream: io.StringIO) -> dict[str, object]:
    return json.loads(stream.getvalue().strip().splitlines()[-1])  # type: ignore[no-any-return]


@pytest.fixture(autouse=True)
def _reset() -> None:
    set_correlation_id(None)


def test_phone_numbers_are_masked_in_every_format() -> None:
    for raw in ["+22997123456", "22997123456", "+229 97 12 34 56", "97-12-34-56"]:
        assert "[phone]" in mask_text(f"client {raw} wrote")
        assert "123456" not in mask_text(raw)


def test_short_numbers_such_as_amounts_survive() -> None:
    assert mask_text("total 3 900 FCFA") == "total 3 900 FCFA"


def test_emails_are_masked() -> None:
    assert mask_text("write to a.b@example.com now") == "write to [email] now"


def test_content_fields_are_redacted() -> None:
    stream = capture()
    logging.getLogger("t").info("received", extra={"text": "bonjour", "kind": "text", "n": 3})
    entry = last_entry(stream)
    assert entry["text"] == "[redacted]"
    assert entry["kind"] == "text"
    assert entry["n"] == 3
    assert "bonjour" not in stream.getvalue()


def test_nested_payload_is_redacted_and_values_masked() -> None:
    stream = capture()
    logging.getLogger("t").info(
        "event", extra={"meta": {"payload": {"text": "hi"}, "who": "+22997123456"}}
    )
    output = stream.getvalue()
    assert "hi" not in json.loads(output)["meta"]["payload"]
    assert "22997123456" not in output


def test_exception_text_is_never_logged_only_its_type() -> None:
    stream = capture()
    try:
        raise ValueError("secret client text +22997123456")
    except ValueError:
        logging.getLogger("t").exception("failed")
    entry = last_entry(stream)
    assert entry["exc_type"] == "ValueError"
    assert "secret client text" not in stream.getvalue()
    assert "22997123456" not in stream.getvalue()


def test_correlation_id_is_attached() -> None:
    stream = capture()
    cid = new_correlation_id()
    logging.getLogger("t").info("hello")
    assert last_entry(stream)["correlation_id"] == cid
