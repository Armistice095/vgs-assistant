"""Find where a piece of text lives in the database.

Used by tests (and available for audits): given a marker string, list every free-text column
that contains it, then compare with the classification registry.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg import sql

from vgs.privacy.classification import REGISTRY, DataClass

Conn = psycopg.Connection[Any]

_TEXTLIKE = ("text", "character varying", "jsonb", "json", "bytea", "ARRAY", "inet")

_ENUMERATED_COLUMNS = """
SELECT cl.relname, a.attname
FROM pg_constraint c
JOIN pg_class cl ON cl.oid = c.conrelid
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
WHERE c.contype = 'c' AND cl.relnamespace = 'public'::regnamespace
  AND array_length(c.conkey, 1) = 1
  AND pg_get_constraintdef(c.oid) ~ '(ANY \\(ARRAY|IN \\()'
"""


def free_text_columns(conn: Conn) -> set[tuple[str, str]]:
    """All text-like columns of the public schema that are not limited to a fixed list of values
    (status, kind, role... are enumerations and cannot hold client text)."""
    enumerated = {(str(r[0]), str(r[1])) for r in conn.execute(_ENUMERATED_COLUMNS).fetchall()}
    rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
        " AND data_type = ANY (%s)",
        (list(_TEXTLIKE),),
    ).fetchall()
    return {(str(t), str(c)) for t, c in rows} - enumerated


def locations_of(conn: Conn, marker: str) -> set[tuple[str, str]]:
    """Every free-text column in which ``marker`` appears."""
    found: set[tuple[str, str]] = set()
    for table, column in sorted(free_text_columns(conn)):
        query = sql.SQL("SELECT 1 FROM {} WHERE {}::text LIKE {} LIMIT 1").format(
            sql.Identifier(table), sql.Identifier(column), sql.Placeholder()
        )
        if conn.execute(query, (f"%{marker}%",)).fetchone():
            found.add((table, column))
    return found


def outside_client_data(locations: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Locations not classified ``client_data``: client text where it must not be."""
    return {(t, c) for t, c in locations if REGISTRY.get(f"{t}.{c}") is not DataClass.CLIENT_DATA}
