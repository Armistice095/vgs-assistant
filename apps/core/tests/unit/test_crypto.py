import pytest
from cryptography.exceptions import InvalidTag

from vgs.crypto import EncryptedBlob, Keyring, StaticKeyProvider, generate_master_key_b64

AAD = b"document-1"


def ring(key_id: str, key_b64: str, retired: dict[str, str] | None = None) -> Keyring:
    return Keyring(StaticKeyProvider.from_b64(key_id, key_b64, retired))


def test_round_trip() -> None:
    keyring = ring("v1", generate_master_key_b64())
    blob = keyring.encrypt(b"identity scan bytes", aad=AAD)
    assert blob.ciphertext != b"identity scan bytes"
    assert keyring.decrypt(blob, aad=AAD) == b"identity scan bytes"


def test_two_encryptions_of_the_same_data_differ() -> None:
    keyring = ring("v1", generate_master_key_b64())
    a = keyring.encrypt(b"same", aad=AAD)
    b = keyring.encrypt(b"same", aad=AAD)
    assert a.ciphertext != b.ciphertext
    assert a.nonce != b.nonce
    assert a.wrapped_dek != b.wrapped_dek


def test_blob_cannot_be_moved_to_another_document() -> None:
    keyring = ring("v1", generate_master_key_b64())
    blob = keyring.encrypt(b"data", aad=b"document-1")
    with pytest.raises(InvalidTag):
        keyring.decrypt(blob, aad=b"document-2")


def test_wrong_master_key_cannot_decrypt() -> None:
    blob = ring("v1", generate_master_key_b64()).encrypt(b"data", aad=AAD)
    other = ring("v1", generate_master_key_b64())
    with pytest.raises(InvalidTag):
        other.decrypt(blob, aad=AAD)


def test_tampered_ciphertext_is_detected() -> None:
    keyring = ring("v1", generate_master_key_b64())
    blob = keyring.encrypt(b"data", aad=AAD)
    tampered = EncryptedBlob(
        blob.key_id,
        blob.wrapped_dek,
        blob.nonce,
        bytes([blob.ciphertext[0] ^ 1]) + blob.ciphertext[1:],
    )
    with pytest.raises(InvalidTag):
        keyring.decrypt(tampered, aad=AAD)


def test_rotation_rewraps_without_touching_the_file() -> None:
    old_key, new_key = generate_master_key_b64(), generate_master_key_b64()
    blob = ring("v1", old_key).encrypt(b"data", aad=AAD)

    rotated = ring("v2", new_key, retired={"v1": old_key})
    assert rotated.needs_rewrap(blob)
    assert rotated.decrypt(blob, aad=AAD) == b"data"  # old files still readable

    rewrapped = rotated.rewrap(blob, aad=AAD)
    assert rewrapped.key_id == "v2"
    assert rewrapped.ciphertext == blob.ciphertext  # stored file unchanged
    assert rewrapped.nonce == blob.nonce
    assert not rotated.needs_rewrap(rewrapped)

    # Once every blob is rewrapped, the retired key can be dropped for good.
    assert ring("v2", new_key).decrypt(rewrapped, aad=AAD) == b"data"
    with pytest.raises(KeyError):
        ring("v2", new_key).decrypt(blob, aad=AAD)


def test_restore_after_machine_rebuild_from_the_password_manager_backup() -> None:
    backup = generate_master_key_b64()  # what the entrepreneur keeps in the password manager
    stored = ring("v1", backup).encrypt(b"piece d'identite", aad=AAD)

    # The VM is destroyed. A brand new process only has the backup and the stored blob.
    fresh_process = ring("v1", backup)
    assert fresh_process.decrypt(stored, aad=AAD) == b"piece d'identite"


def test_master_key_must_be_32_bytes() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        StaticKeyProvider("v1", {"v1": b"too short"})


def test_current_key_must_be_in_the_set() -> None:
    with pytest.raises(ValueError, match="missing"):
        StaticKeyProvider("v2", {"v1": bytes(32)})
