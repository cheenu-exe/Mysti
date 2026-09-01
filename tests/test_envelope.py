"""Unit tests for the AES-256-GCM envelope."""

import pytest

from mysti.exceptions import EncryptionError
from mysti.memory import envelope


def test_generate_key_is_32_bytes():
    assert len(envelope.MAGIC) == 4
    assert len(envelope.generate_key()) == 32


def test_encrypt_decrypt_raw_roundtrip():
    key = envelope.generate_key()
    blob = envelope.encrypt(key, b"hello")
    assert envelope.decrypt(key, blob) == b"hello"


def test_encrypt_raw_rejects_short_key():
    with pytest.raises(EncryptionError):
        envelope.encrypt(b"short", b"data")


def test_raw_decrypt_detects_tampering():
    key = envelope.generate_key()
    blob = bytearray(envelope.encrypt(key, b"hello"))
    blob[-1] ^= 0xFF
    with pytest.raises(EncryptionError):
        envelope.decrypt(key, bytes(blob))


def test_raw_decrypt_rejects_wrong_aad():
    key = envelope.generate_key()
    blob = envelope.encrypt(key, b"hello", b"aad-1")
    with pytest.raises(EncryptionError):
        envelope.decrypt(key, blob, b"aad-2")


def test_seal_unseal_roundtrip_returns_key_version():
    content_key = envelope.generate_key()
    blob = envelope.seal(content_key, 3, b"mysti:record:r1:personal", b"secret text")
    plaintext, version = envelope.unseal(content_key, b"mysti:record:r1:personal", blob)
    assert plaintext == b"secret text"
    assert version == 3


def test_seal_uses_per_record_keys():
    content_key = envelope.generate_key()
    aad = b"mysti:record:r1:personal"
    first = envelope.seal(content_key, 1, aad, b"same")
    second = envelope.seal(content_key, 1, aad, b"same")
    assert first != second, "random per-record keys and nonces must differ"


def test_unseal_rejects_wrong_content_key():
    blob = envelope.seal(envelope.generate_key(), 1, b"aad", b"data")
    with pytest.raises(EncryptionError):
        envelope.unseal(envelope.generate_key(), b"aad", blob)


def test_unseal_rejects_swapped_identity():
    key = envelope.generate_key()
    blob = envelope.seal(key, 1, envelope.record_aad("r1", "personal"), b"data")
    with pytest.raises(EncryptionError):
        envelope.unseal(key, envelope.record_aad("r2", "personal"), blob)


def test_unseal_rejects_tampered_body():
    key = envelope.generate_key()
    blob = bytearray(envelope.seal(key, 1, b"aad", b"attack at dawn"))
    blob[-1] ^= 0x01
    with pytest.raises(EncryptionError):
        envelope.unseal(key, b"aad", bytes(blob))


def test_unseal_rejects_bad_magic():
    key = envelope.generate_key()
    with pytest.raises(EncryptionError):
        envelope.unseal(key, b"aad", b"NOPE" + b"\x00" * 64)


def test_unseal_rejects_unknown_version():
    key = envelope.generate_key()
    blob = bytearray(envelope.seal(key, 1, b"aad", b"data"))
    blob[4] = 99
    with pytest.raises(EncryptionError):
        envelope.unseal(key, b"aad", bytes(blob))
