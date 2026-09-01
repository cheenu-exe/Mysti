"""MYSTI exception hierarchy.

All MYSTI errors derive from MystiError so callers can catch the family while
the API/CLI layers map subclasses to user-facing messages without leaking
sensitive details (e.g. raw crypto errors).
"""


class MystiError(Exception):
    """Base class for all MYSTI errors."""


class StorageError(MystiError):
    """Remote storage operation failed."""


class EncryptionError(MystiError):
    """Encryption or decryption failed (wrong key, tampered data)."""


class KeyManagementError(MystiError):
    """Key hierarchy operation failed (missing key, unknown category)."""


class RecordNotFoundError(MystiError):
    """Requested memory record does not exist (or was deleted)."""


class ValidationError(MystiError):
    """Input failed validation (unknown category, record too large)."""


class LLMError(MystiError):
    """LLM provider call failed."""


class LLMNotConfiguredError(LLMError):
    """No LLM provider is configured."""
