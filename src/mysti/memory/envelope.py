"""AES-256-GCM record envelope.

Layout (all integers big-endian)::

    MAGIC "MYST" (4) | format version (1) | content-key version (4)
    | wrapped-key length (2) | wrapped data key | nonce (12) | ciphertext | tag (16)

A fresh 256-bit data key protects each record; the content key (category key)
wraps it. The record id, category and key version are bound as AAD, so a
ciphertext cannot be swapped between records or categories without failing
authentication.
"""

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from mysti.exceptions import EncryptionError

MAGIC = b"MYST"
FORMAT_VERSION = 1
NONCE_SIZE = 12
KEY_SIZE = 32
_HEADER_SIZE = 4 + 1 + 4 + 2

_ENVELOPE_AAD = b"mysti:envelope"


def generate_key() -> bytes:
    """Generate a random 256-bit key."""
    return os.urandom(KEY_SIZE)


def record_aad(record_id: str, category: str) -> bytes:
    """Additional authenticated data binding a record to its identity."""
    return f"mysti:record:{record_id}:{category}".encode()


def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Encrypt ``plaintext``; returns ``nonce || ciphertext || tag``.

    Used for manifests and indexes (no per-record wrapping).
    """
    if len(key) != KEY_SIZE:
        raise EncryptionError("encryption key must be 32 bytes")
    nonce = os.urandom(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad or None)


def decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    """Decrypt a ``nonce || ciphertext || tag`` blob.

    Raises:
        EncryptionError: On authentication failure or malformed input.
    """
    if len(key) != KEY_SIZE:
        raise EncryptionError("encryption key must be 32 bytes")
    if len(blob) < NONCE_SIZE + 16:
        raise EncryptionError("ciphertext blob is too short")
    nonce, ciphertext = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad or None)
    except InvalidTag as exc:
        raise EncryptionError(
            "decryption failed: data was tampered with or the key is wrong"
        ) from exc


def seal(content_key: bytes, content_key_version: int, aad: bytes, plaintext: bytes) -> bytes:
    """Seal a record with a fresh per-record data key wrapped by ``content_key``."""
    if len(content_key) != KEY_SIZE:
        raise EncryptionError("content key must be 32 bytes")
    data_key = os.urandom(KEY_SIZE)
    wrapped = encrypt(content_key, data_key, aad)
    if len(wrapped) > 0xFFFF:
        raise EncryptionError("wrapped key exceeded envelope capacity")
    header = (
        MAGIC
        + FORMAT_VERSION.to_bytes(1, "big")
        + content_key_version.to_bytes(4, "big")
        + len(wrapped).to_bytes(2, "big")
    )
    body = _encrypt_with_aad(data_key, plaintext, aad)
    return header + wrapped + body


def unseal(content_key: bytes, aad: bytes, blob: bytes) -> tuple[bytes, int]:
    """Open a sealed record; returns ``(plaintext, content_key_version)``.

    Raises:
        EncryptionError: On tampering, wrong key, or malformed envelope.
    """
    if len(blob) < _HEADER_SIZE or not blob.startswith(MAGIC):
        raise EncryptionError("not a valid MYSTI envelope")
    version = blob[4]
    if version != FORMAT_VERSION:
        raise EncryptionError(f"unsupported envelope format version: {version}")
    key_version = int.from_bytes(blob[5:9], "big")
    wrapped_len = int.from_bytes(blob[9:11], "big")
    wrapped = blob[_HEADER_SIZE : _HEADER_SIZE + wrapped_len]
    body = blob[_HEADER_SIZE + wrapped_len :]
    data_key = decrypt(content_key, wrapped, aad)
    return _decrypt_with_aad(data_key, body, aad), key_version


def _encrypt_with_aad(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def _decrypt_with_aad(key: bytes, blob: bytes, aad: bytes) -> bytes:
    if len(blob) < NONCE_SIZE + 16:
        raise EncryptionError("record body is too short")
    nonce, ciphertext = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise EncryptionError(
            "record failed authentication (wrong key, wrong identity, or tampered data)"
        ) from exc
