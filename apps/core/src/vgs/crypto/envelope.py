"""Envelope encryption for documents (AES-256-GCM).

Each file gets its own random data key (DEK). The DEK is wrapped by a master key
identified by ``key_id``. Rotating the master key only re-wraps the small DEKs:
the stored files never need to be re-encrypted.

``aad`` (for example the document id) is bound to both the file and its wrapped
key, so a blob cannot be swapped between documents without detection.

Files are encrypted in one piece. This is fine for the size cap planned for the
core (tens of MB); a streaming mode would be needed above that.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
NONCE_BYTES = 12


def generate_master_key_b64() -> str:
    """Create a new random master key, base64-encoded (for the password manager)."""
    return base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")


class KeyProvider(Protocol):
    """Where master keys come from. A managed KMS can implement this later."""

    @property
    def current_key_id(self) -> str: ...

    def get_key(self, key_id: str) -> bytes: ...


class StaticKeyProvider:
    """Keys held in memory, loaded from the environment at startup."""

    def __init__(self, current_key_id: str, keys: Mapping[str, bytes]) -> None:
        if current_key_id not in keys:
            raise ValueError("the current key id is missing from the key set")
        for key in keys.values():
            if len(key) != KEY_BYTES:
                raise ValueError("master keys must be exactly 32 bytes")
        self._current = current_key_id
        self._keys = dict(keys)

    @classmethod
    def from_b64(
        cls,
        current_key_id: str,
        current_key_b64: str,
        retired_b64: Mapping[str, str] | None = None,
    ) -> StaticKeyProvider:
        keys = {kid: base64.b64decode(value) for kid, value in (retired_b64 or {}).items()}
        keys[current_key_id] = base64.b64decode(current_key_b64)
        return cls(current_key_id, keys)

    @property
    def current_key_id(self) -> str:
        return self._current

    def get_key(self, key_id: str) -> bytes:
        try:
            return self._keys[key_id]
        except KeyError:
            raise KeyError(f"unknown master key id: {key_id}") from None


@dataclass(frozen=True)
class EncryptedBlob:
    key_id: str
    wrapped_dek: bytes  # wrap nonce (12 bytes) + AES-GCM(master, dek)
    nonce: bytes
    ciphertext: bytes


class Keyring:
    def __init__(self, provider: KeyProvider) -> None:
        self._provider = provider

    @property
    def current_key_id(self) -> str:
        return self._provider.current_key_id

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> EncryptedBlob:
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
        key_id = self._provider.current_key_id
        return EncryptedBlob(key_id, self._wrap(key_id, dek, aad), nonce, ciphertext)

    def decrypt(self, blob: EncryptedBlob, *, aad: bytes) -> bytes:
        dek = self._unwrap(blob.key_id, blob.wrapped_dek, aad)
        return AESGCM(dek).decrypt(blob.nonce, blob.ciphertext, aad)

    def needs_rewrap(self, blob: EncryptedBlob) -> bool:
        return blob.key_id != self._provider.current_key_id

    def rewrap(self, blob: EncryptedBlob, *, aad: bytes) -> EncryptedBlob:
        """Wrap the same data key with the current master key (the file is untouched)."""
        dek = self._unwrap(blob.key_id, blob.wrapped_dek, aad)
        key_id = self._provider.current_key_id
        return EncryptedBlob(key_id, self._wrap(key_id, dek, aad), blob.nonce, blob.ciphertext)

    def _wrap(self, key_id: str, dek: bytes, aad: bytes) -> bytes:
        wrap_nonce = os.urandom(NONCE_BYTES)
        wrapped = AESGCM(self._provider.get_key(key_id)).encrypt(wrap_nonce, dek, aad)
        return wrap_nonce + wrapped

    def _unwrap(self, key_id: str, wrapped_dek: bytes, aad: bytes) -> bytes:
        wrap_nonce, wrapped = wrapped_dek[:NONCE_BYTES], wrapped_dek[NONCE_BYTES:]
        return AESGCM(self._provider.get_key(key_id)).decrypt(wrap_nonce, wrapped, aad)
