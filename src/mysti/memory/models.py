"""Pydantic models shared across the memory subsystem."""

from typing import Any

from pydantic import BaseModel, Field


class IndexEntry(BaseModel):
    """Non-sensitive index entry (stored only inside the encrypted index)."""

    id: str
    category: str
    key_version: int
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    size: int
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    """A decrypted memory record as returned to callers."""

    id: str
    category: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class SearchHit(BaseModel):
    """One search result with a short preview."""

    id: str
    category: str
    preview: str
    score: float
    created_at: str


class SessionInfo(BaseModel):
    """Summary of one conversation session."""

    session_id: str
    created_at: str
    last_at: str
    message_count: int


class MessageRecord(BaseModel):
    """A decrypted conversation message."""

    id: str
    session_id: str
    role: str
    content: str
    timestamp: str
