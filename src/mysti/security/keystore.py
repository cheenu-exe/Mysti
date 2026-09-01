"""Secret stores for the master key.

The default backend is the OS keystore via python-keyring (SecretService on
Linux, Keychain on macOS, Credential Manager on Windows). A scrypt-encrypted
file fallback exists for headless machines but is opt-in and loudly warned
about. The in-memory backend is for tests only: keys vanish with the process.
"""

import base64
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from mysti.exceptions import KeyManagementError

logger = logging.getLogger(__name__)

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1


class SecretStore(ABC):
    """Persistence for a single secret: the master key."""

    @abstractmethod
    def get(self) -> bytes | None:
        """Return the stored secret or None if absent."""

    @abstractmethod
    def set(self, value: bytes) -> None:
        """Persist the secret."""

    @abstractmethod
    def delete(self) -> None:
        """Remove the secret if present."""


class KeyringSecretStore(SecretStore):
    """Stores the master key in the OS credential store."""

    def __init__(self, service: str, account: str = "master-key") -> None:
        import keyring

        self._keyring = keyring
        self._service = service
        self._account = account

    def get(self) -> bytes | None:
        encoded = self._keyring.get_password(self._service, self._account)
        return base64.b64decode(encoded) if encoded else None

    def set(self, value: bytes) -> None:
        self._keyring.set_password(
            self._service, self._account, base64.b64encode(value).decode("ascii")
        )

    def delete(self) -> None:
        try:
            self._keyring.delete_password(self._service, self._account)
        except Exception:  # noqa: BLE001 - keyring backends raise various errors
            pass


class InMemorySecretStore(SecretStore):
    """Test/dev-only store; contents disappear with the process."""

    def __init__(self) -> None:
        logger.warning(
            "Using in-memory secret store: keys will be lost on shutdown (tests/dev only)."
        )
        self._secret: bytes | None = None

    def get(self) -> bytes | None:
        return self._secret

    def set(self, value: bytes) -> None:
        self._secret = value

    def delete(self) -> None:
        self._secret = None


class FileSecretStore(SecretStore):
    """Encrypted-file fallback (scrypt + AES-256-GCM). Opt-in and warned about."""

    def __init__(self, path: Path, passphrase: str) -> None:
        logger.warning(
            "Master key stored in a file (%s). This is less secure than an OS keystore.", path
        )
        self._path = Path(path)
        self._passphrase = passphrase

    def _derive(self, salt: bytes) -> bytes:
        kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
        return kdf.derive(self._passphrase.encode("utf-8"))

    def get(self) -> bytes | None:
        if not self._path.is_file():
            return None
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        salt = base64.b64decode(payload["salt"])
        blob = base64.b64decode(payload["data"])
        key = self._derive(salt)
        nonce, ciphertext = blob[:12], blob[12:]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, b"mysti:master-key-file")
        except Exception as exc:  # noqa: BLE001
            raise KeyManagementError("failed to unlock the key file (wrong passphrase?)") from exc

    def set(self, value: bytes) -> None:
        import os

        salt = os.urandom(16)
        key = self._derive(salt)
        nonce = os.urandom(12)
        blob = nonce + AESGCM(key).encrypt(nonce, value, b"mysti:master-key-file")
        payload = {
            "salt": base64.b64encode(salt).decode("ascii"),
            "data": base64.b64encode(blob).decode("ascii"),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload), encoding="utf-8")

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)


def create_secret_store(settings) -> SecretStore:
    """Build the secret store configured by ``MYSTI_SECRET_BACKEND``."""
    if settings.secret_backend == "memory":
        return InMemorySecretStore()
    if settings.secret_backend == "file":
        if not settings.allow_key_file_fallback:
            raise KeyManagementError(
                "file secret backend requires MYSTI_ALLOW_KEY_FILE_FALLBACK=true "
                "(less secure than the OS keystore)"
            )
        if not settings.key_file_passphrase:
            raise KeyManagementError("file secret backend requires MYSTI_KEY_FILE_PASSPHRASE")
        return FileSecretStore(Path(settings.data_dir) / "master.key", settings.key_file_passphrase)
    return KeyringSecretStore(settings.keyring_service)
