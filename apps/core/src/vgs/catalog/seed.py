"""Idempotent, insert-only seed of the starting catalogue.

Insert-only on purpose: once the company edits the catalogue from the dashboard,
re-running the seed must never overwrite their changes. Catalogue version 1 is the
marker: if it exists, the catalogue is left alone. Settings and templates use
``ON CONFLICT DO NOTHING`` for the same reason.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg

from vgs.catalog.seed_data import (
    PROCEDURES,
    SETTINGS,
    TEMPLATES,
    Fee,
    Group,
    ProcedureSeed,
)

_SEED_LOCK_ID = 7_300_001
SEED_NOTE = "Starting values supplied by the client. Not yet validated by Vigo Services."

Conn = psycopg.Connection[Any]


def seed_all(conn: Conn) -> bool:
    """Seed settings, templates and (once) the catalogue.

    Returns True if the catalogue was created, False if it already existed.
    """
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SEED_LOCK_ID,))
    _seed_settings(conn)
    _seed_templates(conn)
    if conn.execute("SELECT 1 FROM catalog_versions WHERE version = 1").fetchone():
        return False
    version_id = _insert_version(conn)
    for sort_order, procedure in enumerate(PROCEDURES, start=1):
        _insert_procedure(conn, version_id, procedure, sort_order)
    return True


def _seed_settings(conn: Conn) -> None:
    for key, value in SETTINGS.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s::jsonb) ON CONFLICT (key) DO NOTHING",
            (key, json.dumps(value)),
        )


def _seed_templates(conn: Conn) -> None:
    for template in TEMPLATES:
        conn.execute(
            "INSERT INTO message_templates"
            " (name, language, body_fr, params_count, purpose, meta_status)"
            " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (name, language) DO NOTHING",
            (
                template.name,
                template.language,
                template.body_fr,
                template.params_count,
                template.purpose,
                template.meta_status,
            ),
        )


def _insert_version(conn: Conn) -> Any:
    row = conn.execute(
        "INSERT INTO catalog_versions (version, status, note) VALUES (1, 'draft', %s) RETURNING id",
        (SEED_NOTE,),
    ).fetchone()
    row = _required(row)
    return row[0]


def _insert_procedure(
    conn: Conn, version_id: Any, procedure: ProcedureSeed, sort_order: int
) -> None:
    row = conn.execute(
        "INSERT INTO procedures (catalog_version_id, code, name_fr, description_fr,"
        " needs_valid_phone, handoff_only, status, sort_order)"
        " VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s) RETURNING id",
        (
            version_id,
            procedure.code,
            procedure.name_fr,
            procedure.description_fr,
            procedure.needs_valid_phone,
            procedure.handoff_only,
            sort_order,
        ),
    ).fetchone()
    row = _required(row)
    procedure_id = row[0]

    if procedure.fee is not None:
        _insert_fee(conn, procedure_id, None, procedure.fee)
    _insert_groups(conn, procedure_id, None, procedure.groups)

    for variant_order, variant in enumerate(procedure.variants, start=1):
        variant_row = conn.execute(
            "INSERT INTO procedure_variants (procedure_id, code, label_fr, handoff_only, status,"
            " sort_order) VALUES (%s, %s, %s, %s, 'draft', %s) RETURNING id",
            (procedure_id, variant.code, variant.label_fr, variant.handoff_only, variant_order),
        ).fetchone()
        variant_row = _required(variant_row)
        variant_id = variant_row[0]
        if variant.fee is not None:
            _insert_fee(conn, procedure_id, variant_id, variant.fee)
        _insert_groups(conn, procedure_id, variant_id, variant.groups)


def _insert_fee(conn: Conn, procedure_id: Any, variant_id: Any, fee: Fee) -> None:
    conn.execute(
        "INSERT INTO fee_rules (procedure_id, variant_id, pricing_mode, parameter_code,"
        " official_fee_xof, official_fee_min_xof, official_fee_max_xof, vigo_fee_xof, status)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft')",
        (
            procedure_id,
            variant_id,
            fee.mode,
            fee.parameter_code,
            fee.official_xof,
            fee.official_min_xof,
            fee.official_max_xof,
            fee.vigo_xof,
        ),
    )


def _insert_groups(
    conn: Conn, procedure_id: Any, variant_id: Any, groups: tuple[Group, ...]
) -> None:
    for position, group in enumerate(groups, start=1):
        row = conn.execute(
            "INSERT INTO requirement_groups (procedure_id, variant_id, position, label_fr, rule,"
            " min_count, condition_note_fr) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                procedure_id,
                variant_id,
                position,
                group.label_fr,
                group.rule,
                group.min_count,
                group.condition_note_fr,
            ),
        ).fetchone()
        row = _required(row)
        for item_position, item in enumerate(group.items, start=1):
            conn.execute(
                "INSERT INTO requirement_items (group_id, code, label_fr, capture_mode, doc_kind,"
                " is_sensitive, is_fallback, status, help_fr, position)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    row[0],
                    item.code,
                    item.label_fr,
                    item.capture_mode,
                    item.doc_kind,
                    item.sensitive,
                    item.fallback,
                    item.status,
                    item.help_fr,
                    item_position,
                ),
            )


def _required(row: Any) -> Any:
    if row is None:
        raise RuntimeError("seed: an INSERT ... RETURNING produced no row")
    return row
