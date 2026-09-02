"""Configuration management for the AI engine.

Phase F adds:
- Environment-based configuration
- Feature flags
- Model configuration
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    model_id: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30


@dataclass
class CacheConfig:
    """Cache configuration."""

    enabled: bool = True
    ttl_seconds: int = 3600
    max_size: int = 1000


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = True
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000


@dataclass
class EngineConfig:
    """Complete AI engine configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    streaming: bool = True
    max_steps: int = 10
    log_level: str = "INFO"


class ConfigManager:
    """Manages AI engine configuration from environment variables."""

    def __init__(self) -> None:
        self._config: EngineConfig | None = None

    def load_from_env(self) -> EngineConfig:
        """Load configuration from environment variables."""
        self._config = EngineConfig(
            llm=LLMConfig(
                model_id=os.getenv("MYSTI_LLM_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("MYSTI_LLM_API_KEY", ""),
                api_base=os.getenv("MYSTI_LLM_API_BASE"),
                max_tokens=int(os.getenv("MYSTI_LLM_MAX_TOKENS", "4096")),
                temperature=float(os.getenv("MYSTI_LLM_TEMPERATURE", "0.7")),
                timeout=int(os.getenv("MYSTI_LLM_TIMEOUT", "30")),
            ),
            cache=CacheConfig(
                enabled=os.getenv("MYSTI_CACHE_ENABLED", "true").lower() == "true",
                ttl_seconds=int(os.getenv("MYSTI_CACHE_TTL", "3600")),
                max_size=int(os.getenv("MYSTI_CACHE_MAX_SIZE", "1000")),
            ),
            rate_limit=RateLimitConfig(
                enabled=os.getenv("MYSTI_RATE_LIMIT_ENABLED", "true").lower() == "true",
                requests_per_minute=int(os.getenv("MYSTI_RATE_LIMIT_RPM", "60")),
                tokens_per_minute=int(os.getenv("MYSTI_RATE_LIMIT_TPM", "100000")),
            ),
            streaming=os.getenv("MYSTI_STREAMING", "true").lower() == "true",
            max_steps=int(os.getenv("MYSTI_MAX_STEPS", "10")),
            log_level=os.getenv("MYSTI_LOG_LEVEL", "INFO"),
        )
        return self._config

    def get_config(self) -> EngineConfig:
        """Get the current configuration, loading from env if needed."""
        if self._config is None:
            return self.load_from_env()
        return self._config

    def set_config(self, config: EngineConfig) -> None:
        """Override the configuration."""
        self._config = config
