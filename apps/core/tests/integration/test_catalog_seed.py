"""The seeded catalogue must reproduce the client's data exactly."""

from __future__ import annotations

import json
from typing import Any

import psycopg
import pytest

from vgs.catalog.reader import get_fee
from vgs.catalog.seed import seed_all

Conn = psycopg.Connection[Any]

# (procedure, variant) -> (official, vigo, total). Copied from the client's brief.
EXPECTED_FEES: dict[tuple[str, str | None], tuple[int, int, int]] = {
    ("birth_certificate_secure", None): (1000, 1500, 2500),
    ("cip", None): (1000, 1500, 2500),
    ("criminal_record", None): (1900, 2000, 3900),
    ("residence_certificate", None): (2000, 2500, 4500),
    ("nationality_certificate", None): (3500, 3000, 6500),
    ("passport_new", None): (30000, 10000, 40000),
    ("passport_renewal", None): (30000, 8000, 38000),
    ("technical_inspection", None): (3000, 5000, 8000),
    ("rccm", "sole_trader"): (10000, 15000, 25000),
    ("rccm", "sarl_suarl"): (22000, 30000, 52000),
    ("rccm", "sa_sas_gie_sci_scp"): (37000, 60000, 97000),
}


@pytest.fixture
def seeded(conn: Conn) -> Conn:
    assert seed_all(conn) is True
    return conn


def _fingerprint(conn: Conn) -> dict[str, list[tuple[Any, ...]]]:
    """Content of every catalogue table without generated ids, to compare two runs."""
    queries = {
        "versions": "SELECT version, status, note FROM catalog_versions ORDER BY version",
        "procedures": "SELECT code, name_fr, status, needs_valid_phone, sort_order FROM procedures"
        " ORDER BY code",
        "variants": "SELECT p.code, v.code, v.status, v.handoff_only FROM procedure_variants v"
        " JOIN procedures p ON p.id = v.procedure_id ORDER BY 1, 2",
        "fees": "SELECT p.code, v.code, f.pricing_mode, f.official_fee_xof, f.vigo_fee_xof,"
        " f.status"
        " FROM fee_rules f JOIN procedures p ON p.id = f.procedure_id"
        " LEFT JOIN procedure_variants v ON v.id = f.variant_id ORDER BY 1, 2",
        "groups": "SELECT p.code, v.code, g.position, g.label_fr, g.rule FROM requirement_groups g"
        " JOIN procedures p ON p.id = g.procedure_id"
        " LEFT JOIN procedure_variants v ON v.id = g.variant_id ORDER BY 1, 2, 3",
        "items": "SELECT p.code, g.position, i.position, i.code, i.label_fr, i.status"
        " FROM requirement_items i JOIN requirement_groups g ON g.id = i.group_id"
        " JOIN procedures p ON p.id = g.procedure_id ORDER BY 1, 2, 3, 4",
        "settings": "SELECT key, value::text FROM settings ORDER BY key",
        "templates": "SELECT name, language, body_fr, meta_status FROM message_templates"
        " ORDER BY name",
    }
    return {name: [tuple(r) for r in conn.execute(q).fetchall()] for name, q in queries.items()}


def test_seed_is_idempotent(conn: Conn) -> None:
    assert seed_all(conn) is True
    first = _fingerprint(conn)
    assert seed_all(conn) is False
    assert _fingerprint(conn) == first


def test_seed_never_overwrites_edits_made_by_the_company(seeded: Conn) -> None:
    seeded.execute("UPDATE fee_rules SET vigo_fee_xof = 1234 WHERE vigo_fee_xof = 2000")
    seeded.execute("UPDATE settings SET value = '45'::jsonb WHERE key = 'batch_window_ms'")
    seed_all(seeded)
    assert seeded.execute(
        "SELECT count(*) FROM fee_rules WHERE vigo_fee_xof = 1234"
    ).fetchone() == (1,)
    assert seeded.execute(
        "SELECT value::text FROM settings WHERE key = 'batch_window_ms'"
    ).fetchone() == ("45",)


@pytest.mark.parametrize(("key", "amounts"), list(EXPECTED_FEES.items()))
def test_fee_matches_the_client_grid(
    seeded: Conn, key: tuple[str, str | None], amounts: tuple[int, int, int]
) -> None:
    official, vigo, total = amounts
    fee = get_fee(seeded, key[0], key[1], allow_draft=True)
    assert fee is not None, key
    assert (fee.official_fee_xof, fee.vigo_fee_xof, fee.total_xof) == (official, vigo, total)
    assert official + vigo == total


def test_tvm_price_depends_on_fiscal_power_and_has_no_invented_bands(seeded: Conn) -> None:
    fee = get_fee(seeded, "vehicle_tvm", allow_draft=True)
    assert fee is not None
    assert fee.pricing_mode == "by_parameter"
    assert fee.official_fee_xof is None  # cannot quote a single total
    assert fee.total_xof is None
    assert (fee.official_fee_min_xof, fee.official_fee_max_xof) == (20000, 60000)
    assert fee.vigo_fee_xof == 3000
    assert seeded.execute("SELECT count(*) FROM fee_parameter_bands").fetchone() == (0,)


def test_every_procedure_has_a_fee_path(seeded: Conn) -> None:
    rows = seeded.execute(
        "SELECT p.code FROM procedures p WHERE NOT EXISTS (SELECT 1 FROM fee_rules f"
        " WHERE f.procedure_id = p.id) AND NOT EXISTS (SELECT 1 FROM procedure_variants v"
        " JOIN fee_rules f ON f.variant_id = v.id WHERE v.procedure_id = p.id)"
    ).fetchall()
    assert rows == []


def _pieces(conn: Conn, procedure: str, variant: str | None = None) -> list[tuple[str, str, str]]:
    rows = conn.execute(
        "SELECT g.label_fr, g.rule, string_agg(i.label_fr, ' | ' ORDER BY i.position)"
        " FROM requirement_groups g JOIN procedures p ON p.id = g.procedure_id"
        " LEFT JOIN procedure_variants v ON v.id = g.variant_id"
        " JOIN requirement_items i ON i.group_id = g.id"
        " WHERE p.code = %s AND v.code IS NOT DISTINCT FROM %s"
        " GROUP BY g.position, g.label_fr, g.rule ORDER BY g.position",
        (procedure, variant),
    ).fetchall()
    return [(str(a), str(b), str(c)) for a, b, c in rows]


def test_criminal_record_needs_identity_and_birth_certificate(seeded: Conn) -> None:
    assert _pieces(seeded, "criminal_record") == [
        ("Pièce d'identité", "one_of", "CIP | Carte d'identité biométrique"),
        ("Acte de naissance sécurisé", "all_of", "Acte de naissance sécurisé"),
    ]


def test_passport_pieces(seeded: Conn) -> None:
    assert _pieces(seeded, "passport_new") == [
        (
            "Pièces à fournir",
            "all_of",
            "Acte de naissance sécurisé | CIP | Certificat de nationalité",
        )
    ]
    assert _pieces(seeded, "passport_renewal") == [
        (
            "Pièces à fournir",
            "all_of",
            "Ancien passeport | Acte de naissance sécurisé | CIP | Certificat de nationalité",
        )
    ]


def test_birth_certificate_fallback_items_are_drafts(seeded: Conn) -> None:
    rows = seeded.execute(
        "SELECT i.label_fr, i.is_fallback, i.status FROM requirement_items i"
        " JOIN requirement_groups g ON g.id = i.group_id JOIN procedures p ON p.id = g.procedure_id"
        " WHERE p.code = 'birth_certificate_secure' ORDER BY i.position"
    ).fetchall()
    fallback = {r[0]: (r[1], r[2]) for r in rows}
    assert fallback["Carte « C'est moi »"] == (True, "draft")
    assert fallback["Certificat FID"] == (True, "draft")
    assert fallback["CIP"] == (False, "confirmed")


def test_text_items_for_vehicles_are_not_files(seeded: Conn) -> None:
    modes = seeded.execute(
        "SELECT DISTINCT i.capture_mode FROM requirement_items i"
        " JOIN requirement_groups g ON g.id = i.group_id JOIN procedures p ON p.id = g.procedure_id"
        " WHERE p.code IN ('vehicle_tvm', 'technical_inspection')"
    ).fetchall()
    assert modes == [("text",)]


def test_rccm_has_three_variants_with_growing_requirements(seeded: Conn) -> None:
    sole = _pieces(seeded, "rccm", "sole_trader")
    sarl = _pieces(seeded, "rccm", "sarl_suarl")
    sa = _pieces(seeded, "rccm", "sa_sas_gie_sci_scp")
    assert len(sole) == 3
    assert sarl[:3] == sole
    assert {g[0] for g in sarl} - {g[0] for g in sole} == {
        "Statuts",
        "Versement ou apports",
        "CIP des associés",
    }
    assert "Statuts notariés" in {g[0] for g in sa}
    quarter = seeded.execute(
        "SELECT g.condition_note_fr FROM requirement_groups g"
        " JOIN procedure_variants v ON v.id = g.variant_id WHERE v.code = 'sa_sas_gie_sci_scp'"
        " AND g.condition_note_fr IS NOT NULL"
    ).fetchall()
    assert quarter == [("Dépôt d'au moins 1/4 du capital.",)]


def test_born_abroad_nationality_case_is_a_handoff(seeded: Conn) -> None:
    assert seeded.execute(
        "SELECT v.handoff_only FROM procedure_variants v JOIN procedures p"
        " ON p.id = v.procedure_id WHERE p.code = 'nationality_certificate'"
        " AND v.code = 'born_abroad'"
    ).fetchone() == (True,)


def test_phone_required_where_the_client_said_so(seeded: Conn) -> None:
    rows = seeded.execute(
        "SELECT code FROM procedures WHERE needs_valid_phone ORDER BY code"
    ).fetchall()
    assert rows == [("birth_certificate_secure",), ("cip",), ("criminal_record",)]


def test_open_questions_are_stored_as_null_not_guessed(seeded: Conn) -> None:
    for key in (
        "retention_days_documents",
        "retention_days_messages",
        "llm_monthly_budget_usd",
        "quote_validity_hours",
    ):
        row = seeded.execute("SELECT value::text FROM settings WHERE key = %s", (key,)).fetchone()
        assert row == ("null",), key
    delay = seeded.execute("SELECT value FROM settings WHERE key = 'default_delay_days'").fetchone()
    assert delay is not None
    assert json.loads(json.dumps(delay[0])) == {
        "min": 3,
        "max": 7,
        "indicative": True,
        "confirmed": False,
    }
    assert seeded.execute(
        "SELECT value::text FROM settings WHERE key = 'payment_order'"
    ).fetchone() == ('"documents_first"',)


def test_the_only_template_is_a_local_test_one(seeded: Conn) -> None:
    rows = seeded.execute("SELECT name, meta_status FROM message_templates").fetchall()
    assert rows == [("dev_out_of_window_test", "local")]
