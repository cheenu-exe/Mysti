"""MYSTI configuration loaded from environment variables (MYSTI_* prefix)."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mysti.exceptions import MystiError

VALID_STORAGE_PROVIDERS = ("local", "s3")
VALID_SECRET_BACKENDS = ("keyring", "file", "memory")
VALID_LLM_PROVIDERS = ("openai", "anthropic", "ollama", "none")
VALID_EMBEDDING_PROVIDERS = ("auto", "sentence-transformers", "api", "hashing", "none")


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

    embedding_provider: str = "auto"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None
    embedding_dimensions: int = 384
    embedding_cache_size: int = 2048
    consolidation_threshold: float = 0.85
    semantic_search_threshold: float = 0.30

    research_enabled: bool = False
    research_briefing_hour: int = 6
    research_briefing_minute: int = 0
    research_collect_minutes: int = 60
    research_consolidation_day: str = "sun"
    research_consolidation_hour: int = 3
    research_min_relevance: float = 5.0
    research_max_briefing_items: int = 20
    interests_path: Path | None = None

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
        if self.embedding_provider not in VALID_EMBEDDING_PROVIDERS:
            raise MystiError(
                f"MYSTI_EMBEDDING_PROVIDER must be one of {VALID_EMBEDDING_PROVIDERS}"
            )
        if self.research_consolidation_day not in (
            "mon", "tue", "wed", "thu", "fri", "sat", "sun",
        ):
            raise MystiError("MYSTI_RESEARCH_CONSOLIDATION_DAY must be a weekday (mon..sun)")
        return self

    @property
    def consolidation_similarity_threshold(self) -> float:
        """Similarity above which consolidation merges memories (0-1)."""
        return max(0.0, min(1.0, self.consolidation_threshold))

    @property
    def briefing_min_relevance(self) -> float:
        """Minimum relevance score for a research item to appear in a briefing."""
        return max(0.0, self.research_min_relevance)

    @property
    def max_record_bytes(self) -> int:
        return self.max_record_kb * 1024

    @property
    def cache_max_bytes(self) -> int:
        return self.cache_max_mb * 1024 * 1024
