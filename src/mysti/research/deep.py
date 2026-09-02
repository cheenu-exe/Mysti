"""Deep research: multi-source investigation with synthesized reports.

A research session fans a topic out across every configured connector and
(optionally, per ``depth``) expands the strongest findings into follow-up
queries, corroborates items that appear on multiple sources, and synthesizes
a markdown report. Sessions are encrypted with the ``research`` category key
and stored at ``mysti/research/{session_id}.enc``.
"""

import json
import re
import uuid
from datetime import UTC, datetime

from mysti.memory import envelope
from mysti.research.connectors import SourceConnector
from mysti.research.models import Findings, ResearchItem, ResearchSession
from mysti.research.relevance import RelevanceEngine
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

SESSION_PREFIX = "mysti/research/"
SESSION_KEY_CATEGORY = "research"
STOPWORDS = frozenset(
    "a an and are as at by for from in into is it of on or that the to with this these those "
    "new how why what when using use your you".split()
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class DeepResearch:
    """Conducts, stores and retrieves deep research sessions."""

    def __init__(
        self,
        connectors: list[SourceConnector],
        relevance: RelevanceEngine,
        keys: KeyManager,
        storage: StorageBackend,
        audit: AuditLog,
    ) -> None:
        self._connectors = connectors
        self._relevance = relevance
        self._keys = keys
        self._storage = storage
        self._audit = audit

    # ----------------------------------------------------------------- storage
    async def _research_key(self) -> bytes:
        names = await self._keys.category_names()
        if SESSION_KEY_CATEGORY not in names:
            await self._keys.create_category(SESSION_KEY_CATEGORY)
        key, _ = await self._keys.get_category_key(SESSION_KEY_CATEGORY)
        return key

    async def _save_session(self, session: ResearchSession) -> None:
        key = await self._research_key()
        aad = f"mysti:research:{session.id}".encode()
        payload = session.model_dump_json().encode("utf-8")
        await self._storage.put(
            f"{SESSION_PREFIX}{session.id}.enc", envelope.encrypt(key, payload, aad)
        )
        self._audit.log("research.save", session.id, metadata={"topic": session.topic})

    async def _load_session(self, session_id: str) -> ResearchSession:
        key = await self._research_key()
        aad = f"mysti:research:{session_id}".encode()
        blob = await self._storage.get(f"{SESSION_PREFIX}{session_id}.enc")
        return ResearchSession.model_validate_json(envelope.decrypt(key, blob, aad))

    # ------------------------------------------------------------------ search
    @staticmethod
    def _extract_terms(text: str, limit: int = 3) -> list[str]:
        """Pull the most informative words out of a finding for expansion."""
        words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{3,}", text.lower())
        counts: dict[str, int] = {}
        for word in words:
            if word not in STOPWORDS:
                counts[word] = counts.get(word, 0) + 1
        return sorted(counts, key=lambda word: counts[word], reverse=True)[:limit]

    async def research(self, topic: str, depth: int = 3) -> ResearchSession:
        """Run a multi-source research session on ``topic``.

        Depth 1-5 controls follow-up expansion: depth 1 searches the topic
        only; each extra level searches derived terms from the strongest
        findings of the previous level (max 2 expansions per level).
        """
        depth = max(1, min(5, depth))
        session = ResearchSession(
            id=str(uuid.uuid4()), topic=topic, started_at=_iso_now(), depth=depth
        )

        def _expandable(text: str) -> list[str]:
            # Terms already present in the topic add no new signal.
            return [t for t in self._extract_terms(text, limit=6) if t not in topic.lower()]
        queries: list[str] = [topic]
        raw_items: list[ResearchItem] = []
        seen_terms: set[str] = set()
        sources_consulted: set[str] = set()

        for level in range(depth):
            next_terms: list[str] = []
            for query in queries:
                for connector in self._connectors:
                    sources_consulted.add(connector.name)
                    try:
                        items = await connector.fetch(query)
                    except Exception:
                        items = []
                    raw_items.extend(items)
                    if level < depth - 1:
                        for item in items:
                            for term in _expandable(item.title):
                                # Skip terms already used in a previous expansion.
                                if term in seen_terms:
                                    continue
                                if len(next_terms) < 2:
                                    seen_terms.add(term)
                                    next_terms.append(term)
            queries = next_terms
            if not queries:
                break

        findings = await self._score_findings(topic, raw_items)
        session.findings = findings
        session.sources_consulted = len(sources_consulted)
        session.completed_at = _iso_now()
        session.confidence = self._confidence(topic, findings)
        session.report = self._render_report(session)
        await self._save_session(session)
        return session

    async def _score_findings(
        self, topic: str, items: list[ResearchItem]
    ) -> list[Findings]:
        """Rank items, corroborate across sources, and extract key findings."""
        scored = await self._relevance.score_all(items)
        findings: list[Findings] = []
        seen: set[str] = set()
        for score, item in scored:
            fp = item.fingerprint()
            if fp in seen:  # dedupe: keep the highest-scored representative
                continue
            seen.add(fp)
            # Corroboration: how many distinct sources reported the same thing.
            corroborations = sum(
                1
                for other in items
                if other.fingerprint() == fp and other.source != item.source
            )
            confidence = min(1.0, 0.4 + score / 25.0 + 0.1 * corroborations)
            citations = sorted(
                {
                    f"{other.source}: {other.url or other.title}"
                    for other in items
                    if other.fingerprint() == fp
                }
            )
            key_finding = f"{item.title} ({item.source})"
            if item.url:
                key_finding += f": {item.url}"
            findings.append(
                Findings(
                    item=item,
                    confidence=round(confidence, 2),
                    key_findings=[key_finding],
                    citations=citations,
                )
            )
        return findings[:25]

    @staticmethod
    def _confidence(topic: str, findings: list[Findings]) -> float:
        if not findings:
            return 0.0
        relevant = [f for f in findings if topic.lower() in f.item.title.lower()]
        base = sum(f.confidence for f in findings) / len(findings)
        return round(min(1.0, base + 0.05 * len(relevant)), 2)

    # ------------------------------------------------------------------ report
    def _render_report(self, session: ResearchSession) -> str:
        lines: list[str] = [
            f"# Research Report: {session.topic}",
            "",
            "## Executive Summary",
            "",
        ]
        if not session.findings:
            lines.append(
                f"No relevant findings for '{session.topic}' across "
                f"{session.sources_consulted} source(s)."
            )
        else:
            top = session.findings[0]
            lines.append(
                f"Analyzed {len(session.findings)} findings from "
                f"{session.sources_consulted} source(s) at depth {session.depth}. "
                f"Most relevant: {top.item.title}."
            )
        lines += ["", "## Key Findings", ""]
        for finding in session.findings[:10]:
            for kf in finding.key_findings:
                lines.append(
                    f"- {kf} _(confidence {finding.confidence:.2f})_"
                )
        lines += ["", "## Detailed Analysis", ""]
        for finding in session.findings:
            lines.append(f"### {finding.item.title}")
            lines.append("")
            if finding.item.content:
                excerpt = finding.item.content[:600]
                lines.append(excerpt + ("..." if len(finding.item.content) > 600 else ""))
                lines.append("")
            meta = [f"source: {finding.item.source}"]
            if finding.item.author:
                meta.append(f"author: {finding.item.author}")
            if finding.item.published_at:
                meta.append(f"published: {finding.item.published_at[:10]}")
            lines.append(f"*{'; '.join(meta)}*")
            lines.append("")
        lines += ["## Sources", ""]
        for finding in session.findings:
            if finding.item.url:
                lines.append(f"- [{finding.item.title}]({finding.item.url})")
        lines += ["", "## Confidence Assessment", ""]
        lines.append(
            f"Overall confidence: **{session.confidence:.2f}** based on "
            f"{len(session.findings)} findings from {session.sources_consulted} source(s)."
        )
        return "\n".join(lines)

    # --------------------------------------------------------------- retrieval
    async def get_report(self, session_id: str) -> dict:
        """Retrieve a stored research session as a dict.

        Raises:
            RecordNotFoundError: If the session does not exist.
        """
        return json.loads((await self._load_session(session_id)).model_dump_json())

    async def list_sessions(self, topic: str | None = None) -> list[dict]:
        """List stored sessions (optionally filtered by topic), newest first."""
        try:
            keys = await self._storage.list(SESSION_PREFIX)
        except Exception:
            keys = []
        sessions: list[dict] = []
        for storage_key in keys:
            session_id = storage_key.removeprefix(SESSION_PREFIX).removesuffix(".enc")
            try:
                session = await self._load_session(session_id)
            except Exception:
                continue
            if topic and topic.lower() not in session.topic.lower():
                continue
            sessions.append(
                {
                    "id": session.id,
                    "topic": session.topic,
                    "started_at": session.started_at,
                    "completed_at": session.completed_at,
                    "sources_consulted": session.sources_consulted,
                    "findings": len(session.findings),
                    "confidence": session.confidence,
                }
            )
        sessions.sort(key=lambda s: s["started_at"], reverse=True)
        return sessions
