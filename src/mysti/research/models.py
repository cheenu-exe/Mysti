"""Pydantic models for the research subsystem."""

from typing import Any

from pydantic import BaseModel, Field


class ResearchItem(BaseModel):
    """One piece of research content fetched from an external source."""

    id: str = ""
    source: str
    title: str
    content: str = ""
    url: str | None = None
    author: str | None = None
    published_at: str | None = None
    fetched_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Stable identity used for cross-source deduplication."""
        return (self.url or f"{self.source}:{self.title}").strip().lower()


class Findings(BaseModel):
    """A deep-research finding: an item enriched with analysis metadata."""

    item: ResearchItem
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    key_findings: list[str] = Field(default_factory=list)


class ResearchSession(BaseModel):
    """One deep-research run over a topic."""

    id: str
    topic: str
    started_at: str
    completed_at: str | None = None
    depth: int = 3
    sources_consulted: int = 0
    findings: list[Findings] = Field(default_factory=list)
    report: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
