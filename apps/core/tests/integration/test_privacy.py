"""Client text must live only where the registry says, and erasure must reach all of it."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest

from vgs.privacy.classification import PLANNED, REGISTRY, DataClass, client_data_columns
from vgs.privacy.erasure import ERASED_TEXT, erase_contact
from vgs.privacy.retention import (
    mark_inbound_event_done,
    purge_failed_payloads,
    purge_stale_unprocessed_payloads,
)
from vgs.privacy.scan import free_text_columns, locations_of, outside_client_data

Conn = psycopg.Connection[Any]

MARKER = "ZXQ-CLIENT-TEXT-7731"
PHONE = "+22997000042"
OTHER_PHONE = "+22997000099"


def test_every_free_text_column_is_classified(conn: Conn) -> None:
    """Adding a text/json column without deciding its data class must fail the build."""
    in_schema = {f"{t}.{c}" for t, c in free_text_columns(conn)}
    assert in_schema - set(REGISTRY) == set(), "unclassified free-text columns"
    assert set(REGISTRY) - in_schema == set(), "registry entries that no longer exist"


def test_planned_tables_are_not_in_the_schema_yet(conn: Conn) -> None:
    """When a planned table is created, its columns must move from PLANNED to REGISTRY."""
    in_schema = {f"{t}.{c}" for t, c in free_text_columns(conn)}
    assert not (set(PLANNED) & in_schema), "move these columns from PLANNED to REGISTRY"


def test_registry_values_are_valid_classes() -> None:
    assert set(REGISTRY.values()) | set(PLANNED.values()) <= set(DataClass)


def test_append_only_tables_only_have_technical_columns() -> None:
    for table in ("audit_log", "consent_events"):
        classes = {cls for key, cls in REGISTRY.items() if key.startswith(f"{table}.")}
        assert DataClass.CLIENT_DATA not in classes, table


def _account(conn: Conn) -> UUID:
    row = conn.execute(
        "INSERT INTO channel_accounts (channel, external_account_id, label)"
        " VALUES ('console', 'privacy-test', 'x') RETURNING id"
    ).fetchone()
    assert row is not None
    return cast(UUID, row[0])


def _client(conn: Conn, account: UUID, phone: str, marker: str) -> tuple[UUID, UUID]:
    """A contact with client text in every client_data column. Returns (contact, conversation)."""
    contact = conn.execute(
        "INSERT INTO contacts (channel_account_id, channel_contact_id, display_name)"
        " VALUES (%s, %s, %s) RETURNING id",
        (account, phone, f"Name {marker}"),
    ).fetchone()
    assert contact is not None
    conversation = conn.execute(
        "INSERT INTO conversations (contact_id, summary, mode_reason) VALUES (%s, %s, %s)"
        " RETURNING id",
        (contact[0], f"summary {marker}", f"reason {marker}"),
    ).fetchone()
    assert conversation is not None
    event = conn.execute(
        "INSERT INTO inbound_events (channel_account_id, dedupe_key, event_type, payload,"
        " correlation_id) VALUES (%s, %s, 'message', %s::jsonb, gen_random_uuid()) RETURNING id",
        (
            account,
            f"wamid.{uuid4().hex}",
            json.dumps({"message": {"contact": {"contact_id": phone}, "text": f"hi {marker}"}}),
        ),
    ).fetchone()
    assert event is not None
    conn.execute(
        "INSERT INTO messages (conversation_id, direction, sender, kind, text, inbound_event_id)"
        " VALUES (%s, 'in', 'client', 'text', %s, %s)",
        (conversation[0], f"bonjour {marker}", event[0]),
    )
    conn.execute(
        "INSERT INTO alerts (type, summary, conversation_id) VALUES ('missing_info', %s, %s)",
        (f"client says {marker}", conversation[0]),
    )
    return cast(UUID, contact[0]), cast(UUID, conversation[0])


def test_client_text_only_exists_in_columns_classified_as_client_data(conn: Conn) -> None:
    account = _account(conn)
    _client(conn, account, PHONE, MARKER)
    found = locations_of(conn, MARKER)
    assert found == set(client_data_columns()) - {("contacts", "channel_contact_id")}
    assert outside_client_data(found) == set()


def test_the_guard_catches_client_text_in_the_wrong_place(conn: Conn) -> None:
    """Proves the check is not vacuous: a leak into a config column is reported."""
    conn.execute("INSERT INTO catalog_versions (version, note) VALUES (201, %s)", (MARKER,))
    assert outside_client_data(locations_of(conn, MARKER)) == {("catalog_versions", "note")}


def test_the_phone_number_only_lives_in_client_data_columns(conn: Conn) -> None:
    account = _account(conn)
    _client(conn, account, PHONE, MARKER)
    found = locations_of(conn, PHONE)
    assert found == {("contacts", "channel_contact_id"), ("inbound_events", "payload")}
    assert outside_client_data(found) == set()


def test_erasure_removes_the_client_everywhere_and_spares_others(conn: Conn) -> None:
    account = _account(conn)
    contact, conversation = _client(conn, account, PHONE, MARKER)
    other_contact, _ = _client(conn, account, OTHER_PHONE, "OTHER-MARKER-5512")

    assert locations_of(conn, MARKER) != set()  # there is something to erase
    assert erase_contact(conn, contact) is True

    # No trace of the text or of the phone number anywhere in the database.
    assert locations_of(conn, MARKER) == set()
    assert locations_of(conn, PHONE) == set()
    # The other client is untouched.
    assert locations_of(conn, "OTHER-MARKER-5512") != set()
    assert locations_of(conn, OTHER_PHONE) != set()
    # Structure that is not personal is kept.
    assert conn.execute(
        "SELECT count(*), bool_and(text IS NULL) FROM messages WHERE conversation_id = %s",
        (conversation,),
    ).fetchone() == (1, True)
    assert conn.execute(
        "SELECT summary FROM alerts WHERE conversation_id = %s", (conversation,)
    ).fetchone() == (ERASED_TEXT,)
    row = conn.execute(
        "SELECT channel_contact_id, display_name, anonymized_at IS NOT NULL FROM contacts"
        " WHERE id = %s",
        (contact,),
    ).fetchone()
    assert row == (f"erased:{contact}", None, True)
    assert other_contact != contact
    # Traced in the audit log, without any content.
    audit = conn.execute(
        "SELECT action, target_type, meta::text FROM audit_log WHERE target_id = %s", (contact,)
    ).fetchall()
    assert audit == [("erasure.executed", "contact", "{}")]


def test_erasure_is_idempotent(conn: Conn) -> None:
    account = _account(conn)
    contact, _ = _client(conn, account, PHONE, MARKER)
    assert erase_contact(conn, contact) is True
    assert erase_contact(conn, contact) is False
    assert conn.execute(
        "SELECT count(*) FROM audit_log WHERE target_id = %s", (contact,)
    ).fetchone() == (1,)


def test_erasing_an_unknown_contact_is_an_error(conn: Conn) -> None:
    with pytest.raises(LookupError):
        erase_contact(conn, UUID("00000000-0000-0000-0000-000000000000"))


def test_the_same_person_can_write_again_after_erasure(conn: Conn) -> None:
    account = _account(conn)
    contact, _ = _client(conn, account, PHONE, MARKER)
    erase_contact(conn, contact)
    again = conn.execute(
        "INSERT INTO contacts (channel_account_id, channel_contact_id)"
        " VALUES (%s, %s) RETURNING id",
        (account, PHONE),
    ).fetchone()
    assert again is not None and again[0] != contact


def _event(conn: Conn, account: UUID, key: str, status: str, age_days: int) -> UUID:
    row = conn.execute(
        "INSERT INTO inbound_events (channel_account_id, dedupe_key, event_type, payload, status,"
        " correlation_id, received_at) VALUES (%s, %s, 'message', %s::jsonb, %s,"
        " gen_random_uuid(), now() - make_interval(days => %s)) RETURNING id",
        (account, key, json.dumps({"text": MARKER}), status, age_days),
    ).fetchone()
    assert row is not None
    return cast(UUID, row[0])


def _has_payload(conn: Conn, event: UUID) -> bool:
    row = conn.execute("SELECT payload IS NOT NULL FROM inbound_events WHERE id = %s", (event,))
    return bool(row.fetchone()[0])  # type: ignore[index]


def test_payload_is_wiped_when_the_event_is_done(conn: Conn) -> None:
    account = _account(conn)
    event = _event(conn, account, "e1", "processing", 0)
    assert _has_payload(conn, event)
    mark_inbound_event_done(conn, event)
    assert not _has_payload(conn, event)
    assert conn.execute(
        "SELECT status, payload_purged_at IS NOT NULL FROM inbound_events WHERE id = %s", (event,)
    ).fetchone() == ("done", True)


def test_failed_payloads_are_wiped_after_the_retention_only(conn: Conn) -> None:
    account = _account(conn)
    recent = _event(conn, account, "f1", "failed", 2)
    old = _event(conn, account, "f2", "dead", 8)
    assert purge_failed_payloads(conn, older_than_days=7) == 1
    assert _has_payload(conn, recent)
    assert not _has_payload(conn, old)


def test_events_stuck_in_progress_do_not_keep_client_text_forever(conn: Conn) -> None:
    account = _account(conn)
    fresh = _event(conn, account, "s1", "queued", 0)
    stuck = _event(conn, account, "s2", "processing", 3)
    assert purge_stale_unprocessed_payloads(conn, older_than_days=2) == 1
    assert _has_payload(conn, fresh)
    assert not _has_payload(conn, stuck)
    assert conn.execute("SELECT status FROM inbound_events WHERE id = %s", (stuck,)).fetchone() == (
        "dead",
    )
