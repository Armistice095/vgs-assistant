"""Master key handling: loading, rotation from configuration, backup check, VM rebuild."""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.exceptions import InvalidTag

from vgs.config import Settings
from vgs.crypto import EncryptedBlob, Keyring, generate_master_key_b64
from vgs.crypto.keys import KeyConfigError, fingerprint, provider_from_settings
from vgs.crypto.keytool import main as keytool

AAD = b"document-42"


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_provider_is_built_from_the_environment_settings() -> None:
    key = generate_master_key_b64()
    keyring = Keyring(provider_from_settings(settings(master_key_id="v1", master_key_b64=key)))
    blob = keyring.encrypt(b"scan", aad=AAD)
    assert keyring.decrypt(blob, aad=AAD) == b"scan"


def test_missing_key_is_a_clear_error() -> None:
    with pytest.raises(KeyConfigError, match="MASTER_KEY_B64 is not set"):
        provider_from_settings(settings())


@pytest.mark.parametrize("bad", ["not base64 !!", base64.b64encode(b"short").decode()])
def test_malformed_keys_are_rejected_without_echoing_them(bad: str) -> None:
    with pytest.raises(KeyConfigError) as excinfo:
        provider_from_settings(settings(master_key_id="v1", master_key_b64=bad))
    assert bad not in str(excinfo.value)


def test_retired_keys_must_be_a_json_mapping() -> None:
    key = generate_master_key_b64()
    for bad in ["not json", json.dumps(["v1"]), json.dumps({"v1": 3})]:
        with pytest.raises(KeyConfigError):
            provider_from_settings(
                settings(master_key_id="v2", master_key_b64=key, master_keys_retired_json=bad)
            )


def test_current_key_cannot_also_be_retired() -> None:
    key = generate_master_key_b64()
    with pytest.raises(KeyConfigError, match="must not also be listed"):
        provider_from_settings(
            settings(
                master_key_id="v1",
                master_key_b64=key,
                master_keys_retired_json=json.dumps({"v1": key}),
            )
        )


def test_rotation_through_configuration_keeps_old_files_readable() -> None:
    old, new = generate_master_key_b64(), generate_master_key_b64()
    blob = Keyring(
        provider_from_settings(settings(master_key_id="v1", master_key_b64=old))
    ).encrypt(b"scan", aad=AAD)
    rotated = Keyring(
        provider_from_settings(
            settings(
                master_key_id="v2",
                master_key_b64=new,
                master_keys_retired_json=json.dumps({"v1": old}),
            )
        )
    )
    assert rotated.decrypt(blob, aad=AAD) == b"scan"
    rewrapped = rotated.rewrap(blob, aad=AAD)
    assert rewrapped.key_id == "v2"
    # After the rewrap the old key is no longer needed.
    only_new = Keyring(provider_from_settings(settings(master_key_id="v2", master_key_b64=new)))
    assert only_new.decrypt(rewrapped, aad=AAD) == b"scan"


def test_vm_rebuild_restores_a_stored_piece_from_the_password_manager_copy() -> None:
    """The whole machine is lost. Only two things survive, both outside the VM: the encrypted
    objects (R2 + database rows) and the backup of the key in the password manager."""
    original_key = generate_master_key_b64()
    password_manager_copy = original_key  # what the entrepreneur saved

    running = Keyring(
        provider_from_settings(settings(master_key_id="v1", master_key_b64=original_key))
    )
    blob = running.encrypt(b"identity scan bytes", aad=AAD)
    object_store = {"documents/42": blob.ciphertext}  # survives (R2)
    database_row = (blob.key_id, blob.wrapped_dek, blob.nonce)  # survives (Postgres)
    del running, original_key  # the VM and its environment are gone

    rebuilt = Keyring(
        provider_from_settings(settings(master_key_id="v1", master_key_b64=password_manager_copy))
    )
    restored = EncryptedBlob(*database_row[:3], ciphertext=object_store["documents/42"])
    assert rebuilt.decrypt(restored, aad=AAD) == b"identity scan bytes"


def test_without_the_backup_the_piece_is_unrecoverable() -> None:
    blob = Keyring(
        provider_from_settings(
            settings(master_key_id="v1", master_key_b64=generate_master_key_b64())
        )
    ).encrypt(b"x", aad=AAD)
    lost = Keyring(
        provider_from_settings(
            settings(master_key_id="v1", master_key_b64=generate_master_key_b64())
        )
    )
    with pytest.raises(InvalidTag):
        lost.decrypt(blob, aad=AAD)


def test_fingerprint_is_stable_short_and_key_specific() -> None:
    key = generate_master_key_b64()
    assert fingerprint(key) == fingerprint(key)
    assert len(fingerprint(key)) == 8
    assert fingerprint(key) != fingerprint(generate_master_key_b64())
    assert key not in fingerprint(key)


def test_keytool_generate_fingerprint_and_verify(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert keytool(["generate", "v7"]) == 0
    out = capsys.readouterr()
    lines = dict(line.split("=", 1) for line in out.out.strip().splitlines())
    assert lines["MASTER_KEY_ID"] == "v7"
    key = lines["MASTER_KEY_B64"]
    assert out.err.strip() == f"fingerprint={fingerprint(key)}"

    monkeypatch.setenv("MASTER_KEY_B64", key)
    assert keytool(["fingerprint"]) == 0
    assert capsys.readouterr().out.strip() == fingerprint(key)
    assert keytool(["verify", key]) == 0
    assert capsys.readouterr().out.strip() == "MATCH"
    assert keytool(["verify", generate_master_key_b64()]) == 1
    assert capsys.readouterr().out.strip() == "DIFFERENT"


def test_keytool_without_a_key_in_the_environment_fails_cleanly(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MASTER_KEY_B64", raising=False)
    assert keytool(["fingerprint"]) == 2
    assert "not set" in capsys.readouterr().err
