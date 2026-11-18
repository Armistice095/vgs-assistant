"""What the assistant is allowed to see of the catalogue.

Production rule: only entries of the PUBLISHED catalogue version whose status is
``confirmed`` are usable. ``allow_draft`` (development and tests only, see
``Settings.allow_draft_catalog``) widens this to the latest version, any status.
This is the single place where that rule lives; callers never query the catalogue
tables directly for the bot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

Conn = psycopg.Connection[Any]


@dataclass(frozen=True)
class FeeView:
    procedure_code: str
    variant_code: str | None
    pricing_mode: str
    official_fee_xof: int | None
    official_fee_min_xof: int | None
    official_fee_max_xof: int | None
    vigo_fee_xof: int

    @property
    def total_xof(self) -> int | None:
        if self.official_fee_xof is None:
            return None
        return self.official_fee_xof + self.vigo_fee_xof


_VERSION_FILTER_PUBLISHED = "cv.status = 'published'"
_VERSION_FILTER_LATEST = "cv.version = (SELECT max(version) FROM catalog_versions)"


def _scope(allow_draft: bool) -> tuple[str, str, str]:
    """Return (version filter, procedure status filter, fee status filter)."""
    if allow_draft:
        return _VERSION_FILTER_LATEST, "TRUE", "TRUE"
    return _VERSION_FILTER_PUBLISHED, "p.status = 'confirmed'", "f.status = 'confirmed'"


def usable_procedure_codes(conn: Conn, *, allow_draft: bool) -> list[str]:
    version, procedure_status, _ = _scope(allow_draft)
    # The interpolated fragments are constants chosen by _scope(), never user input.
    rows = conn.execute(
        "SELECT p.code FROM procedures p JOIN catalog_versions cv ON cv.id = p.catalog_version_id"  # noqa: S608
        f" WHERE {version} AND {procedure_status} ORDER BY p.sort_order"
    ).fetchall()
    return [str(r[0]) for r in rows]


def get_fee(
    conn: Conn, procedure_code: str, variant_code: str | None = None, *, allow_draft: bool
) -> FeeView | None:
    """Fee of a usable procedure, or None when it is unknown or not usable (-> alert the team)."""
    version, procedure_status, fee_status = _scope(allow_draft)
    row = conn.execute(
        "SELECT p.code, v.code, f.pricing_mode, f.official_fee_xof, f.official_fee_min_xof,"  # noqa: S608
        " f.official_fee_max_xof, f.vigo_fee_xof"
        " FROM fee_rules f"
        " JOIN procedures p ON p.id = f.procedure_id"
        " JOIN catalog_versions cv ON cv.id = p.catalog_version_id"
        " LEFT JOIN procedure_variants v ON v.id = f.variant_id"
        f" WHERE {version} AND {procedure_status} AND {fee_status}"
        " AND p.code = %s AND v.code IS NOT DISTINCT FROM %s",
        (procedure_code, variant_code),
    ).fetchone()
    if row is None:
        return None
    return FeeView(*row)
