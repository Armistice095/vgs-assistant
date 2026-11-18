from __future__ import annotations

import uuid
from typing import Any

import psycopg
from alembic import command
from psycopg import sql

from tests.integration.conftest import alembic_config
from vgs.db import psycopg_dsn


def _public_tables(conn: psycopg.Connection[Any]) -> set[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    return {str(r[0]) for r in rows}


def test_upgrade_downgrade_upgrade_on_an_empty_database(test_database_url: str) -> None:
    """Up, fully down, up again, on a database that nothing else uses."""
    scratch = f"vgs_mig_{uuid.uuid4().hex[:8]}"
    admin = psycopg.connect(psycopg_dsn(test_database_url), autocommit=True)
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(scratch)))
        base, _, _ = test_database_url.rpartition("/")
        scratch_url = f"{base}/{scratch}"
        config = alembic_config(scratch_url)

        command.upgrade(config, "head")
        with psycopg.connect(psycopg_dsn(scratch_url)) as check:
            after_up = _public_tables(check)
        assert {"contacts", "messages", "procedures", "audit_log", "alerts"} <= after_up

        command.downgrade(config, "base")
        with psycopg.connect(psycopg_dsn(scratch_url)) as check:
            assert _public_tables(check) == {"alembic_version"}

        command.upgrade(config, "head")
        with psycopg.connect(psycopg_dsn(scratch_url)) as check:
            assert _public_tables(check) == after_up
    finally:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(scratch))
        )
        admin.close()
