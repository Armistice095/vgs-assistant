import pytest
from pydantic import ValidationError

from vgs.config import Environment, Settings

GOOD_SECRET = "x" * 40


def make(**overrides: object) -> Settings:
    base: dict[str, object] = {"_env_file": None}
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


def test_development_defaults_are_permissive() -> None:
    settings = make()
    assert settings.vgs_env is Environment.DEVELOPMENT
    assert settings.reply_window_hours == 24
    assert settings.allow_draft_catalog is False


def test_draft_catalog_allowed_in_development_and_test() -> None:
    assert make(vgs_env="development", allow_draft_catalog=True).allow_draft_catalog
    assert make(vgs_env="test", allow_draft_catalog=True).allow_draft_catalog


@pytest.mark.parametrize("env", ["staging", "production"])
def test_draft_catalog_refused_when_deployed(env: str) -> None:
    with pytest.raises(ValidationError, match="ALLOW_DRAFT_CATALOG"):
        make(
            vgs_env=env,
            allow_draft_catalog=True,
            database_url="postgresql+psycopg://u@h/d",
            master_key_b64="a",
            channel_hmac_secret=GOOD_SECRET,
        )


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_requires_core_secrets(env: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        make(vgs_env=env)
    message = str(excinfo.value)
    assert "DATABASE_URL" in message
    assert "MASTER_KEY_B64" in message
    assert "CHANNEL_HMAC_SECRET" in message


def test_short_hmac_secret_refused_when_deployed() -> None:
    with pytest.raises(ValidationError, match="CHANNEL_HMAC_SECRET"):
        make(
            vgs_env="staging",
            database_url="postgresql+psycopg://u@h/d",
            master_key_b64="a",
            channel_hmac_secret="short",
        )


def test_baileys_forbidden_in_production_but_not_staging() -> None:
    common: dict[str, object] = {
        "database_url": "postgresql+psycopg://u@h/d",
        "master_key_b64": "a",
        "channel_hmac_secret": GOOD_SECRET,
        "channel_adapter": "whatsapp_baileys",
    }
    with pytest.raises(ValidationError, match="forbidden in production"):
        make(vgs_env="production", **common)
    assert make(vgs_env="staging", **common).channel_adapter == "whatsapp_baileys"


def test_reply_window_can_never_be_zero_or_infinite() -> None:
    with pytest.raises(ValidationError):
        make(reply_window_hours=0)
    with pytest.raises(ValidationError):
        make(reply_window_hours=-1)


def test_secrets_are_not_printed() -> None:
    settings = make(channel_hmac_secret=GOOD_SECRET)
    assert GOOD_SECRET not in repr(settings)
