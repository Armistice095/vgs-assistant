"""Erasure of a client's data on request.

Everything classified ``client_data`` in ``classification.REGISTRY`` is wiped. What stays is
what no longer identifies the person: ids, timestamps, statuses, amounts and the append-only
journals (which hold only technical columns by construction).

The contact identifier is NOT replaced by a hash: a hash of a phone number can be brute-forced
because the space of numbers is small. It is replaced by ``erased:<contact id>``, which is not
derived from the number. If the person writes again later they become a new contact.

Documents are not covered yet (the table arrives with step 2/4): ``classification.PLANNED``
records that its files and encrypted names must be wiped here, and the schema test fails
until the table is classified.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg

Conn = psycopg.Connection[Any]

ERASED_TEXT = "[erased]"


def erase_contact(conn: Conn, contact_id: UUID, *, executed_by: UUID | None = None) -> bool:
    """Erase a contact's data. Returns False if it was already erased. Runs in the caller's
    transaction: the caller commits, so the erasure is all-or-nothing."""
    row = conn.execute(
        "SELECT channel_contact_id, anonymized_at FROM contacts WHERE id = %s FOR UPDATE",
        (contact_id,),
    ).fetchone()
    if row is None:
        raise LookupError("unknown contact")
    original_identifier, anonymized_at = row
    if anonymized_at is not None:
        return False

    conn.execute(
        "UPDATE messages SET text = NULL WHERE conversation_id IN"
        " (SELECT id FROM conversations WHERE contact_id = %s)",
        (contact_id,),
    )
    conn.execute(
        "UPDATE conversations SET summary = NULL, mode_reason = NULL WHERE contact_id = %s",
        (contact_id,),
    )
    conn.execute(
        "UPDATE alerts SET summary = %s WHERE conversation_id IN"
        " (SELECT id FROM conversations WHERE contact_id = %s)",
        (ERASED_TEXT, contact_id),
    )
    # Raw events carry the identifier and the text. They are matched on the identifier itself,
    # wherever it appears in the payload, so that no event is missed.
    conn.execute(
        "UPDATE inbound_events SET payload = NULL, payload_purged_at = now()"
        " WHERE payload IS NOT NULL AND position(%s in payload::text) > 0",
        (original_identifier,),
    )
    conn.execute(
        "UPDATE contacts SET channel_contact_id = %s, display_name = NULL,"
        " erasure_requested_at = coalesce(erasure_requested_at, now()), anonymized_at = now()"
        " WHERE id = %s",
        (f"erased:{contact_id}", contact_id),
    )
    conn.execute(
        "INSERT INTO audit_log (actor_type, actor_id, action, target_type, target_id)"
        " VALUES (%s, %s, 'erasure.executed', 'contact', %s)",
        ("staff" if executed_by else "system", executed_by, contact_id),
    )
    return True
