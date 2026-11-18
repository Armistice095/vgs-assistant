"""A draft catalogue entry must never be usable by the assistant in production."""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from vgs.catalog.reader import get_fee, usable_procedure_codes
from vgs.catalog.seed import seed_all

Conn = psycopg.Connection[Any]


@pytest.fixture
def seeded(conn: Conn) -> Conn:
    seed_all(conn)
    return conn


def test_fresh_seed_exposes_nothing_in_production_mode(seeded: Conn) -> None:
    assert usable_procedure_codes(seeded, allow_draft=False) == []
    assert get_fee(seeded, "criminal_record", allow_draft=False) is None


def test_development_mode_exposes_the_seed(seeded: Conn) -> None:
    codes = usable_procedure_codes(seeded, allow_draft=True)
    assert "criminal_record" in codes
    assert len(codes) == 10
    fee = get_fee(seeded, "criminal_record", allow_draft=True)
    assert fee is not None
    assert fee.total_xof == 3900


def test_a_published_version_still_hides_draft_procedures(seeded: Conn) -> None:
    seeded.execute("UPDATE catalog_versions SET status = 'published' WHERE version = 1")
    assert usable_procedure_codes(seeded, allow_draft=False) == []


def test_confirmed_procedure_is_usable_but_its_draft_price_is_not(seeded: Conn) -> None:
    seeded.execute("UPDATE catalog_versions SET status = 'published' WHERE version = 1")
    seeded.execute("UPDATE procedures SET status = 'confirmed' WHERE code = 'criminal_record'")
    assert usable_procedure_codes(seeded, allow_draft=False) == ["criminal_record"]
    assert get_fee(seeded, "criminal_record", allow_draft=False) is None  # fee still draft


def test_confirmed_procedure_and_fee_are_quotable(seeded: Conn) -> None:
    seeded.execute("UPDATE catalog_versions SET status = 'published' WHERE version = 1")
    seeded.execute("UPDATE procedures SET status = 'confirmed' WHERE code = 'criminal_record'")
    seeded.execute(
        "UPDATE fee_rules SET status = 'confirmed' WHERE procedure_id ="
        " (SELECT id FROM procedures WHERE code = 'criminal_record')"
    )
    fee = get_fee(seeded, "criminal_record", allow_draft=False)
    assert fee is not None
    assert fee.total_xof == 3900


def test_unpublished_version_is_invisible_even_if_everything_is_confirmed(seeded: Conn) -> None:
    seeded.execute("UPDATE procedures SET status = 'confirmed'")
    seeded.execute("UPDATE fee_rules SET status = 'confirmed'")
    assert usable_procedure_codes(seeded, allow_draft=False) == []
