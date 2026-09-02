"""Conversation summarization: LLM-assisted with a deterministic fallback.

Long conversations are compressed into a structured summary (key topics, key
facts, decisions, action items) plus a short prose overview. When an LLM is
configured it produces the summary from a strict-JSON prompt; without one,
or when the model call fails, an extractive fallback ranks sentences and
content words so the feature still works offline (Phase 0 default). The
model name is recorded on the summary so consumers know which path produced
it.

Summaries are stored encrypted under the reserved ``conversation`` category
key at ``mysti/summaries/{session_id}.enc`` and can be refreshed
incrementally: only messages added since the previous summary are re-read,
the new findings are merged into the stored ones and ``version`` is bumped.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from mysti.exceptions import RecordNotFoundError, ValidationError
from mysti.memory import envelope
from mysti.memory.conversations import ConversationStore
from mysti.memory.models import ConversationSummary
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

logger = logging.getLogger(__name__)

SUMMARY_PREFIX = "mysti/summaries/"
SUMMARY_KEY_CATEGORY = "conversation"
CHUNK_SIZE = 20  # progressive: messages summarized per chunk

STOPWORDS = frozenset(
    "a about after all also am an and any are as at be because been before being but by can "
    "could did do does done down each for from had has have he her his how i if in into is it "
    "its just like me my new no not now of on one or our out over she should so some such than "
    "that the their them then there these they this those to up us very was we were what when "
    "where which while who will with would you your".split()
)
DECISION_MARKERS = ("we decided", "decision", "decided", "agreed", "concluded", "confirmed")
ACTION_MARKERS = (
    "remember to",
    "to do",
    "todo",
    "next step",
    "next steps",
    "plan to",
    "need to",
    "should",
    "must",
    "will",
    "follow up",
)

@dataclass
class _PartialSummary:
    """Raw findings from one summarization step (before being merged)."""

    model: str
    summary: str = ""
    key_topics: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    original_length: int = 0
    message_count: int = 0


class LLMClientProto(Protocol):
    """Minimal LLM surface used by the summarizer."""

    async def complete(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        ...


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _dedupe(items: list[str]) -> list[str]:
    """Remove duplicate items preserving the first occurrence and case."""
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        lowered = item.strip().lower()
        if lowered and lowered not in seen:
            seen.add(lowered)
            unique.append(item.strip())
    return unique


def _split_sentences(text: str) -> list[str]:
    """Split into sentences on common sentence boundaries."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 2]


def _sentence_score(sentence: str, frequencies: Counter[str]) -> float:
    """Rank a sentence by the frequency of its content words."""
    words = [w for w in re.findall(r"[a-z0-9']+", sentence.lower()) if w not in STOPWORDS]
    if not words:
        return 0.0
    return sum(frequencies.get(w, 0) for w in words) / (len(words) ** 0.5)


def _extractive_summary(messages: list[dict[str, str]]) -> _PartialSummary:
    """Deterministic offline summarization of a message list."""
    text = "\n".join(f"{role}: {content}" for role, content in messages)
    words = [
        w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) >= 3 and w not in STOPWORDS
    ]
    frequencies = Counter(words)
    topics = [word for word, _ in frequencies.most_common(12)]

    sentences = _split_sentences(text)
    scored = sorted(
        ((_sentence_score(s, frequencies), s) for s in sentences),
        key=lambda pair: pair[0],
        reverse=True,
    )
    facts = [sentence for score, sentence in scored[:5] if score > 0]

    decisions = [s for s in sentences if any(marker in s.lower() for marker in DECISION_MARKERS)]
    actions = [
        s
        for s in sentences
        if len(s) < 140 and any(marker in s.lower() for marker in ACTION_MARKERS)
    ]
    decisions = _dedupe(decisions)[:6]
    actions = _dedupe(actions)[:6]

    overview = (
        f"This conversation covered: {', '.join(topics[:6]) or 'general discussion'}. "
        "Key points below."
    )
    return _PartialSummary(
        model="extractive",
        summary=overview,
        key_topics=topics[:10],
        key_facts=facts,
        decisions=decisions,
        action_items=actions,
        original_length=sum(len(content) for _, content in messages),
        message_count=len(messages),
    )


def _parse_json_object(reply: str) -> dict:
    """Extract a JSON object from an LLM reply (tolerates fences/whitespace)."""
    text = reply.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in LLM summary reply")
    return json.loads(text[start : end + 1])


async def _llm_summary(messages: list[dict[str, str]], llm: LLMClientProto) -> _PartialSummary:
    """Ask the LLM for a strict-JSON summary; raises on failure."""
    transcript = "\n".join(f"{role}: {content}" for role, content in messages)
    prompt = (
        "Summarize this conversation. Respond with STRICT JSON only, exactly:\n"
        '{"summary": "1-2 sentence overview", "key_topics": [...], '
        '"key_facts": [...], "decisions": [...], "action_items": [...]}\n'
        "Each list item must be a concise standalone bullet.\n\n"
        f"--- conversation ---\n{transcript}"
    )
    reply = await llm.complete([{"role": "user", "content": prompt}])
    data = _parse_json_object(reply)
    return _PartialSummary(
        model="llm",
        summary=str(data.get("summary", "")).strip(),
        key_topics=[str(t) for t in data.get("key_topics", [])],
        key_facts=[str(f) for f in data.get("key_facts", [])],
        decisions=[str(d) for d in data.get("decisions", [])],
        action_items=[str(a) for a in data.get("action_items", [])],
        original_length=sum(len(content) for _, content in messages),
        message_count=len(messages),
    )
class ConversationSummarizer:
    """Compresses conversations and stores summaries encrypted at rest."""

    def __init__(
        self,
        conversations: ConversationStore,
        keys: KeyManager,
        storage: StorageBackend,
        audit: AuditLog,
        llm: LLMClientProto | None = None,
    ) -> None:
        self._conversations = conversations
        self._keys = keys
        self._storage = storage
        self._audit = audit
        self._llm = llm

    # ---------------------------------------------------------------- storage
    async def _summary_key(self) -> bytes:
        key, _ = await self._keys.get_category_key(SUMMARY_KEY_CATEGORY)
        return key

    def _storage_key(self, session_id: str) -> str:
        return f"{SUMMARY_PREFIX}{session_id}.enc"

    def _aad(self, session_id: str) -> bytes:
        return f"mysti:summary:{session_id}".encode()

    async def _load(self, session_id: str) -> ConversationSummary | None:
        try:
            blob = await self._storage.get(self._storage_key(session_id))
        except RecordNotFoundError:
            return None
        key = await self._summary_key()
        payload, _ = envelope.unseal(key, self._aad(session_id), blob)
        return ConversationSummary.model_validate_json(payload)

    async def _save(self, summary: ConversationSummary) -> None:
        key, version = await self._keys.get_category_key(SUMMARY_KEY_CATEGORY)
        blob = envelope.seal(
            key,
            version,
            self._aad(summary.session_id),
            summary.model_dump_json().encode("utf-8"),
        )
        await self._storage.put(self._storage_key(summary.session_id), blob)

    # ------------------------------------------------------------- summarization
    @staticmethod
    def _llm_is_usable(llm: LLMClientProto) -> bool:
        """True when the client is not the 'no provider configured' placeholder."""
        return "Unconfigured" not in type(llm).__name__

    async def _summarize_messages(self, messages, llm: LLMClientProto | None) -> _PartialSummary:
        """Summarize one message batch: LLM first, extractive fallback."""
        transcript = [{"role": message.role, "content": message.content} for message in messages]
        active = llm or self._llm
        if active is not None and self._llm_is_usable(active):
            try:
                return await _llm_summary(transcript, active)
            except Exception as exc:  # noqa: BLE001 - any LLM failure falls back
                logger.warning("LLM summarization failed, using extractive fallback: %s", exc)
        return _extractive_summary(transcript)

    def _build_model(
        self, partial: _PartialSummary, session_id: str, version: int
    ) -> ConversationSummary:
        """Materialize a stored summary from one (possibly merged) partial."""
        summary_text = partial.summary.strip()
        summary_length = len(summary_text) + sum(
            len(item)
            for item in (partial.key_topics + partial.key_facts
                         + partial.decisions + partial.action_items)
        )
        original = partial.original_length or 1
        return ConversationSummary(
            session_id=session_id,
            created_at=_iso_now(),
            updated_at=_iso_now(),
            message_count=partial.message_count,
            model=partial.model,
            version=version,
            summary=summary_text,
            key_topics=partial.key_topics,
            key_facts=partial.key_facts,
            decisions=partial.decisions,
            action_items=partial.action_items,
            original_length=partial.original_length,
            summary_length=summary_length,
            compression_ratio=round(1.0 - summary_length / original, 4),
        )

    def _merge_incremental(
        self, existing: ConversationSummary, fresh: _PartialSummary, session_id: str
    ) -> ConversationSummary:
        """Merge newly summarized messages into a stored summary (version+1)."""
        merged = _PartialSummary(
            model=fresh.model,
            original_length=existing.original_length + fresh.original_length,
            message_count=existing.message_count + fresh.message_count,
        )
        overviews = [s for s in (existing.summary, fresh.summary) if s]
        merged.summary = "\n\n".join(_dedupe(overviews))
        merged.key_topics = _dedupe(existing.key_topics + fresh.key_topics)[:10]
        merged.key_facts = _dedupe(existing.key_facts + fresh.key_facts)[:10]
        merged.decisions = _dedupe(existing.decisions + fresh.decisions)[:8]
        merged.action_items = _dedupe(existing.action_items + fresh.action_items)[:8]
        return self._build_model(merged, session_id, version=existing.version + 1)
# ---------------------------------------------------------------- public API
    async def summarize(
        self, session_id: str, *, force: bool = False, llm: LLMClientProto | None = None
    ) -> ConversationSummary:
        """Summarize (or incrementally update) a conversation session.

        Progressive path: when a summary already exists, only messages added
        since it was written are summarized again and merged in, bumping
        ``version``. Otherwise messages are processed in chunks of
        ``CHUNK_SIZE`` and the chunk summaries are combined.

        Raises:
            RecordNotFoundError: If the conversation session does not exist.
            ValidationError: If the session has no messages.
        """
        messages = await self._conversations.get_messages(session_id, limit=10**9)
        if not messages:
            raise ValidationError(f"conversation {session_id} has no messages")
        existing = await self._load(session_id)
        if existing is not None and not force:
            fresh = messages[existing.message_count:]
            if not fresh:
                return existing
            fresh_partial = await self._summarize_messages(fresh, llm)
            summary = self._merge_incremental(existing, fresh_partial, session_id)
        else:
            partials: list[_PartialSummary] = []
            for start in range(0, len(messages), CHUNK_SIZE):
                chunk = await self._summarize_messages(messages[start : start + CHUNK_SIZE], llm)
                partials.append(chunk)
            summary = self._merge_chunks(partials, session_id)
        await self._save(summary)
        self._audit.log(
            "memory.summarize",
            session_id,
            metadata={
                "messages": len(messages),
                "version": summary.version,
                "model": summary.model,
            },
        )
        return summary

    def _merge_chunks(
        self, partials: list[_PartialSummary], session_id: str
    ) -> ConversationSummary:
        """Combine progressive chunk summaries into one stored summary."""
        if not partials:
            raise ValueError("no chunks to merge")
        merged = _PartialSummary(
            model=partials[0].model,
            original_length=sum(p.original_length for p in partials),
            message_count=sum(p.message_count for p in partials),
        )
        overviews: list[str] = []
        for partial in partials:
            merged.key_topics.extend(partial.key_topics)
            merged.key_facts.extend(partial.key_facts)
            merged.decisions.extend(partial.decisions)
            merged.action_items.extend(partial.action_items)
            if partial.summary:
                overviews.append(partial.summary)
        merged.summary = "\n\n".join(_dedupe(overviews))
        merged.key_topics = _dedupe(merged.key_topics)[:10]
        merged.key_facts = _dedupe(merged.key_facts)[:10]
        merged.decisions = _dedupe(merged.decisions)[:8]
        merged.action_items = _dedupe(merged.action_items)[:8]
        return self._build_model(merged, session_id, version=1)

    async def get(self, session_id: str) -> ConversationSummary:
        """Return the stored summary for ``session_id``.

        Raises:
            RecordNotFoundError: If no summary exists for the session.
        """
        summary = await self._load(session_id)
        if summary is None:
            raise RecordNotFoundError(f"no summary for conversation {session_id}")
        return summary

    async def list_summaries(self, limit: int = 20) -> list[dict]:
        """Return compact metadata for recent summaries, newest first."""
        try:
            keys = await self._storage.list(SUMMARY_PREFIX)
        except Exception:  # noqa: BLE001 - missing prefixes are not fatal
            keys = []
        summaries: list[ConversationSummary] = []
        for storage_key in sorted(keys, reverse=True):
            session_id = storage_key.removeprefix(SUMMARY_PREFIX).removesuffix(".enc")
            try:
                summary = await self._load(session_id)
            except Exception:  # noqa: BLE001 - skip unreadable summaries
                continue
            if summary is not None:
                summaries.append(summary)
        summaries.sort(key=lambda summary: summary.updated_at, reverse=True)
        return [
            {
                "session_id": s.session_id,
                "updated_at": s.updated_at,
                "message_count": s.message_count,
                "model": s.model,
                "version": s.version,
                "key_topics": s.key_topics,
            }
            for s in summaries[:limit]
        ]
