"""The database itself must refuse what the business rules forbid."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from psycopg import errors

Conn = psycopg.Connection[Any]


def _account(conn: Conn, channel: str = "console", production: bool = False) -> Any:
    row = conn.execute(
        "INSERT INTO channel_accounts (channel, external_account_id, label, is_production)"
        " VALUES (%s, %s, 'test', %s) RETURNING id",
        (channel, f"acc-{channel}-{production}", production),
    ).fetchone()
    assert row is not None
    return row[0]


def _conversation(conn: Conn) -> Any:
    account = _account(conn)
    contact = conn.execute(
        "INSERT INTO contacts (channel_account_id, channel_contact_id) VALUES (%s, 'c1')"
        " RETURNING id",
        (account,),
    ).fetchone()
    assert contact is not None
    conv = conn.execute(
        "INSERT INTO conversations (contact_id) VALUES (%s) RETURNING id", (contact[0],)
    ).fetchone()
    assert conv is not None
    return conv[0]


def test_baileys_account_can_never_be_production(conn: Conn) -> None:
    with pytest.raises(errors.CheckViolation, match="baileys_never_production"):
        _account(conn, "whatsapp_baileys", production=True)


def test_baileys_account_is_fine_outside_production(conn: Conn) -> None:
    assert _account(conn, "whatsapp_baileys", production=False)


def test_reply_window_can_never_be_zero(conn: Conn) -> None:
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO channel_accounts (channel, external_account_id, label, reply_window_hours)"
            " VALUES ('console', 'z', 'z', 0)"
        )


def test_duplicate_inbound_event_is_rejected_and_on_conflict_makes_it_a_noop(conn: Conn) -> None:
    account = _account(conn)
    insert = (
        "INSERT INTO inbound_events (channel_account_id, dedupe_key, event_type, correlation_id)"
        " VALUES (%s, 'wamid.1', 'message', gen_random_uuid())"
    )
    conn.execute(insert, (account,))
    cur = conn.execute(insert + " ON CONFLICT DO NOTHING", (account,))
    assert cur.rowcount == 0
    with pytest.raises(errors.UniqueViolation):
        conn.execute(insert, (account,))


def test_outbound_id_makes_sending_idempotent(conn: Conn) -> None:
    conv = _conversation(conn)
    insert = (
        "INSERT INTO messages (conversation_id, direction, sender, kind, outbound_id)"
        " VALUES (%s, 'out', 'bot', 'text', '11111111-1111-1111-1111-111111111111')"
    )
    conn.execute(insert, (conv,))
    with pytest.raises(errors.UniqueViolation):
        conn.execute(insert, (conv,))


def test_a_message_from_the_client_cannot_be_outbound_and_vice_versa(conn: Conn) -> None:
    conv = _conversation(conn)
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO messages (conversation_id, direction, sender, kind)"
            " VALUES (%s, 'in', 'bot', 'text')",
            (conv,),
        )
    conn.rollback()
    conv = _conversation(conn)
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO messages (conversation_id, direction, sender, kind)"
            " VALUES (%s, 'out', 'client', 'text')",
            (conv,),
        )


def test_only_one_published_catalogue_version(conn: Conn) -> None:
    conn.execute("INSERT INTO catalog_versions (version, status) VALUES (101, 'published')")
    with pytest.raises(errors.UniqueViolation):
        conn.execute("INSERT INTO catalog_versions (version, status) VALUES (102, 'published')")


def test_published_version_cannot_go_back_to_draft(conn: Conn) -> None:
    conn.execute("INSERT INTO catalog_versions (version, status) VALUES (103, 'published')")
    with pytest.raises(errors.RaiseException, match="cannot go back to draft"):
        conn.execute("UPDATE catalog_versions SET status = 'draft' WHERE version = 103")


def test_fiscal_power_bands_cannot_overlap(conn: Conn) -> None:
    conn.execute("INSERT INTO catalog_versions (version) VALUES (104)")
    conn.execute(
        "INSERT INTO procedures (catalog_version_id, code, name_fr)"
        " SELECT id, 'tvm_t', 'TVM' FROM catalog_versions WHERE version = 104"
    )
    conn.execute(
        "INSERT INTO fee_rules (procedure_id, pricing_mode, parameter_code, vigo_fee_xof)"
        " SELECT id, 'by_parameter', 'fiscal_power', 3000 FROM procedures WHERE code = 'tvm_t'"
    )
    band = (
        "INSERT INTO fee_parameter_bands (fee_rule_id, min_value, max_value, official_fee_xof)"
        " SELECT id, %s, %s, %s FROM fee_rules WHERE parameter_code = 'fiscal_power'"
    )
    conn.execute(band, (1, 4, 20000))
    conn.execute(band, (5, 7, 30000))
    with pytest.raises(errors.ExclusionViolation):
        conn.execute(band, (7, 9, 40000))


def test_fixed_fee_needs_an_official_amount(conn: Conn) -> None:
    conn.execute("INSERT INTO catalog_versions (version) VALUES (105)")
    conn.execute(
        "INSERT INTO procedures (catalog_version_id, code, name_fr)"
        " SELECT id, 'x', 'X' FROM catalog_versions WHERE version = 105"
    )
    with pytest.raises(errors.CheckViolation, match="fixed_needs_official"):
        conn.execute(
            "INSERT INTO fee_rules (procedure_id, pricing_mode, vigo_fee_xof)"
            " SELECT id, 'fixed', 100 FROM procedures WHERE code = 'x'"
        )


def test_only_one_open_alert_per_dedupe_key(conn: Conn) -> None:
    insert = "INSERT INTO alerts (type, summary, dedupe_key) VALUES ('missing_info', 's', 'k1')"
    conn.execute(insert)
    with pytest.raises(errors.UniqueViolation):
        conn.execute(insert)
    conn.rollback()
    conn.execute(insert)
    conn.execute("UPDATE alerts SET status = 'resolved' WHERE dedupe_key = 'k1'")
    conn.execute(insert)  # allowed again once the first one is resolved


def test_audit_log_is_append_only(conn: Conn) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor_type, action, target_type, target_id)"
        " VALUES ('system', 'config.changed', 'settings', gen_random_uuid())"
    )
    with pytest.raises(errors.RaiseException, match="append-only"):
        conn.execute("UPDATE audit_log SET action = 'dossier.viewed'")
    conn.rollback()
    conn.execute(
        "INSERT INTO audit_log (actor_type, action, target_type, target_id)"
        " VALUES ('system', 'config.changed', 'settings', gen_random_uuid())"
    )
    with pytest.raises(errors.RaiseException, match="append-only"):
        conn.execute("DELETE FROM audit_log")
    conn.rollback()
    with pytest.raises(errors.RaiseException, match="append-only"):
        conn.execute("TRUNCATE audit_log")


def test_consent_events_are_append_only(conn: Conn) -> None:
    account = _account(conn)
    contact = conn.execute(
        "INSERT INTO contacts (channel_account_id, channel_contact_id) VALUES (%s, 'c2')"
        " RETURNING id",
        (account,),
    ).fetchone()
    assert contact is not None
    conn.execute(
        "INSERT INTO consent_events (contact_id, status, text_version)"
        " VALUES (%s, 'granted', 'v0')",
        (contact[0],),
    )
    with pytest.raises(errors.RaiseException, match="append-only"):
        conn.execute("UPDATE consent_events SET status = 'withdrawn'")
