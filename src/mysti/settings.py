"""MYSTI configuration loaded from environment variables (MYSTI_* prefix)."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mysti.exceptions import MystiError

VALID_STORAGE_PROVIDERS = ("local", "s3")
VALID_SECRET_BACKENDS = ("keyring", "file", "memory")
VALID_LLM_PROVIDERS = ("openai", "anthropic", "ollama", "none")


class Settings(BaseSettings):
    """Application settings sourced from MYSTI_* environment variables / .env."""

    model_config = SettingsConfigDict(env_prefix="MYSTI_", env_file=".env", extra="ignore")

    storage_provider: str = "local"
    storage_bucket: str = "mysti"
    storage_endpoint: str | None = None
    storage_region: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None

    cache_max_mb: int = 256
    cache_ttl: int = 86400

    max_record_kb: int = 1024

    data_dir: Path = Path.home() / ".mysti"
    log_level: str = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_token: str | None = None

    secret_backend: str = "keyring"
    keyring_service: str = "mysti"
    allow_key_file_fallback: bool = False
    key_file_passphrase: str | None = None

    llm_provider: str = "none"
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if self.storage_provider not in VALID_STORAGE_PROVIDERS:
            raise MystiError(f"MYSTI_STORAGE_PROVIDER must be one of {VALID_STORAGE_PROVIDERS}")
        if self.storage_provider == "s3":
            missing = [
                name
                for name, value in (
                    ("MYSTI_STORAGE_BUCKET", self.storage_bucket),
                    ("MYSTI_STORAGE_ACCESS_KEY", self.storage_access_key),
                    ("MYSTI_STORAGE_SECRET_KEY", self.storage_secret_key),
                )
                if not value
            ]
            if missing:
                raise MystiError(f"s3 storage provider requires: {', '.join(missing)}")
        if self.secret_backend not in VALID_SECRET_BACKENDS:
            raise MystiError(f"MYSTI_SECRET_BACKEND must be one of {VALID_SECRET_BACKENDS}")
        if self.llm_provider not in VALID_LLM_PROVIDERS:
            raise MystiError(f"MYSTI_LLM_PROVIDER must be one of {VALID_LLM_PROVIDERS}")
        return self

    @property
    def max_record_bytes(self) -> int:
        return self.max_record_kb * 1024

    @property
    def cache_max_bytes(self) -> int:
        return self.cache_max_mb * 1024 * 1024
