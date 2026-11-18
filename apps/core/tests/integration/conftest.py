"""Integration tests run against a real Postgres (TEST_DATABASE_URL).

The schema is rebuilt once per session by running the real Alembic migrations, so the
tests exercise exactly what production will run. Each test works inside a transaction
that is rolled back, so tests never see each other's data.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from vgs.db import psycopg_dsn

CORE_DIR = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    config = Config(str(CORE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(CORE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def migrated_url(test_database_url: str) -> str:
    with psycopg.connect(psycopg_dsn(test_database_url), autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    command.upgrade(alembic_config(test_database_url), "head")
    return test_database_url


@pytest.fixture
def conn(migrated_url: str) -> Iterator[psycopg.Connection[Any]]:
    connection = psycopg.connect(psycopg_dsn(migrated_url))
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
