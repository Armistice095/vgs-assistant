"""`.env.example` must list every setting the core reads, and contain no real secret."""

from __future__ import annotations

import re
from pathlib import Path

from vgs.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[4] / ".env.example"


def _keys() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).split("#")[0].strip()
    return values


def test_every_core_setting_is_documented_in_env_example() -> None:
    documented = set(_keys())
    needed = {name.upper() for name in Settings.model_fields}
    assert needed - documented == set()


def test_env_example_has_no_filled_secret() -> None:
    values = _keys()
    for name in (
        "MASTER_KEY_B64",
        "CHANNEL_HMAC_SECRET",
        "ANTHROPIC_API_KEY",
        "S3_SECRET_ACCESS_KEY",
    ):
        assert values[name] == "", f"{name} must be empty in the example"


def test_env_example_never_enables_drafts_by_default() -> None:
    assert _keys()["ALLOW_DRAFT_CATALOG"] in ("false", "")
