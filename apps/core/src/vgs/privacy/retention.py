"""Retention of raw inbound events.

Decision (ADR 0005): the raw payload of an inbound event is only needed to process it. It is
wiped as soon as the event is done; events that failed are kept a little longer to debug, then
wiped too. Identifiers and statuses stay (they are what makes processing idempotent).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg

Conn = psycopg.Connection[Any]

DEFAULT_FAILED_PAYLOAD_RETENTION_DAYS = 7


def mark_inbound_event_done(conn: Conn, event_id: UUID) -> None:
    """Mark an event processed and wipe its payload in the same statement."""
    conn.execute(
        "UPDATE inbound_events SET status = 'done', processed_at = now(),"
        " payload = NULL, payload_purged_at = now() WHERE id = %s",
        (event_id,),
    )


def purge_failed_payloads(
    conn: Conn, *, older_than_days: int = DEFAULT_FAILED_PAYLOAD_RETENTION_DAYS
) -> int:
    """Wipe the payload of failed or dead events older than the retention. Returns the count."""
    cur = conn.execute(
        "UPDATE inbound_events SET payload = NULL, payload_purged_at = now()"
        " WHERE payload IS NOT NULL AND status IN ('failed', 'dead')"
        " AND received_at < now() - make_interval(days => %s)",
        (older_than_days,),
    )
    return cur.rowcount


def purge_stale_unprocessed_payloads(conn: Conn, *, older_than_days: int = 2) -> int:
    """Safety net: an event stuck in a non-final state must not keep client text forever."""
    cur = conn.execute(
        "UPDATE inbound_events SET payload = NULL, payload_purged_at = now(),"
        " status = CASE WHEN status IN ('received', 'queued', 'processing') THEN 'dead'"
        " ELSE status END"
        " WHERE payload IS NOT NULL AND status IN ('received', 'queued', 'processing')"
        " AND received_at < now() - make_interval(days => %s)",
        (older_than_days,),
    )
    return cur.rowcount
