"""Small database helpers."""

from __future__ import annotations


def psycopg_dsn(url: str) -> str:
    """Turn a SQLAlchemy-style URL (``postgresql+psycopg://``) into a plain libpq URL."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)
