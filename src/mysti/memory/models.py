"""Pydantic models shared across the memory subsystem."""

from typing import Any

from pydantic import BaseModel, Field


class IndexEntry(BaseModel):
    """Non-sensitive index entry (stored only inside the encrypted index).

    Embeddings and access statistics live here — never plaintext content — so
    filtering, ranking and consolidation can run without decrypting records.
    """

    id: str
    category: str
    key_version: int
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    size: int
    content_hash: str
    tags: list[str] = Field(default_factory=list)
    source: str = "chat"
    importance: int = Field(default=5, ge=1, le=10)
    access_count: int = 0
    last_accessed: str | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    """A decrypted memory record as returned to callers."""

    id: str
    category: str
    content: str
    content_hash: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "chat"
    importance: int = Field(default=5, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    last_accessed: str | None = None
    access_count: int = 0
    embedding: list[float] | None = None
    deleted_at: str | None = None


class SearchHit(BaseModel):
    """One search result with a short preview, match kind and explanation.

    ``match_type`` is one of ``semantic`` (vector similarity only), `keyword``
    (exact-term match only) or ``hybrid`` (both signals contributed). The
    explanation is a human-readable sentence describing why the record matched.
    """

    id: str
    category: str
    preview: str
    score: float
    created_at: str
    match_type: str = "hybrid"
    explanation: str = ""


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


class ConversationSummary(BaseModel):
    """Compressed representation of a conversation session.

    ``original_length`` is the total character count of the summarized
    messages; ``compression_ratio`` is ``1 - summary_length/original_length``.
    ``model`` records what produced the summary (``extractive`` fallback or an
    LLM provider/model string) and ``version`` increases on each incremental
    update so consumers can tell summaries apart.
    """

    session_id: str
    created_at: str
    updated_at: str
    message_count: int
    model: str
    version: int = 1
    summary: str = ""
    key_topics: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    original_length: int = 0
    summary_length: int = 0
    compression_ratio: float = 0.0
