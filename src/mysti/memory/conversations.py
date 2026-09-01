"""Encrypted conversation sessions.

Each message is sealed individually with the reserved ``conversation`` key so
single-message retrieval decrypts only that message. Session indexes are
encrypted and hold no content.
"""

import json
import uuid
from datetime import UTC, datetime

from mysti.exceptions import RecordNotFoundError, ValidationError
from mysti.memory import envelope
from mysti.memory.models import MessageRecord, SessionInfo
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

SESSIONS_KEY = "mysti/conversations/sessions.enc"
SESSIONS_AAD = b"mysti:conversation-sessions"
VALID_ROLES = ("user", "assistant", "system")
_CONVERSATION_CATEGORY = "conversation"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def message_path(session_id: str, message_id: str) -> str:
    """Remote storage path for one encrypted message blob."""
    return f"mysti/conversations/{session_id}/{message_id}.enc"


def session_index_path(session_id: str) -> str:
    """Remote storage path for a session's encrypted message-id list."""
    return f"mysti/conversations/{session_id}/index.enc"


class ConversationStore:
    """Encrypted conversation persistence with context-window building."""

    def __init__(self, storage: StorageBackend, keys: KeyManager, audit: AuditLog) -> None:
        self._storage = storage
        self._keys = keys
        self._audit = audit

    async def _conversation_key(self) -> bytes:
        key, _ = await self._keys.get_category_key(_CONVERSATION_CATEGORY)
        return key

    async def _load_sessions(self) -> dict[str, dict]:
        try:
            blob = await self._storage.get(SESSIONS_KEY)
        except RecordNotFoundError:
            return {}
        data = envelope.decrypt(await self._conversation_key(), blob, SESSIONS_AAD)
        return json.loads(data)

    async def _save_sessions(self, sessions: dict[str, dict]) -> None:
        payload = json.dumps(sessions).encode("utf-8")
        blob = envelope.encrypt(await self._conversation_key(), payload, SESSIONS_AAD)
        await self._storage.put(SESSIONS_KEY, blob)

    async def _load_session_index(self, session_id: str) -> list[str]:
        try:
            blob = await self._storage.get(session_index_path(session_id))
        except RecordNotFoundError:
            return []
        aad = f"mysti:session-index:{session_id}".encode()
        return json.loads(envelope.decrypt(await self._conversation_key(), blob, aad))

    async def _save_session_index(self, session_id: str, message_ids: list[str]) -> None:
        aad = f"mysti:session-index:{session_id}".encode()
        payload = json.dumps(message_ids).encode("utf-8")
        blob = envelope.encrypt(await self._conversation_key(), payload, aad)
        await self._storage.put(session_index_path(session_id), blob)

    async def start_session(self) -> str:
        """Create a new conversation session and return its id."""
        session_id = str(uuid.uuid4())
        now = _iso_now()
        sessions = await self._load_sessions()
        sessions[session_id] = {"created_at": now, "last_at": now, "message_count": 0}
        await self._save_sessions(sessions)
        self._audit.log("conversation.start", session_id)
        return session_id

    async def add_message(self, session_id: str, role: str, content: str) -> MessageRecord:
        """Encrypt and persist one message; updates session bookkeeping."""
        if role not in VALID_ROLES:
            raise ValidationError(f"invalid message role: {role!r}")
        sessions = await self._load_sessions()
        if session_id not in sessions:
            raise RecordNotFoundError(f"conversation session not found: {session_id}")
        message_id = str(uuid.uuid4())
        now = _iso_now()
        key = await self._conversation_key()
        payload = json.dumps({"role": role, "content": content, "timestamp": now}).encode("utf-8")
        blob = envelope.seal(key, 1, f"mysti:message:{session_id}:{message_id}".encode(), payload)
        path = message_path(session_id, message_id)
        await self._storage.put(path, blob)
        message_ids = await self._load_session_index(session_id)
        message_ids.append(message_id)
        await self._save_session_index(session_id, message_ids)
        sessions[session_id]["last_at"] = now
        sessions[session_id]["message_count"] = len(message_ids)
        await self._save_sessions(sessions)
        self._audit.log(
            "conversation.add_message",
            message_id,
            metadata={"session_id": session_id, "role": role},
        )
        return MessageRecord(
            id=message_id, session_id=session_id, role=role, content=content, timestamp=now
        )

    async def get_messages(
        self, session_id: str, limit: int = 50, offset: int = 0
    ) -> list[MessageRecord]:
        """Return decrypted messages for a session, oldest first."""
        sessions = await self._load_sessions()
        if session_id not in sessions:
            raise RecordNotFoundError(f"conversation session not found: {session_id}")
        message_ids = (await self._load_session_index(session_id))[offset : offset + limit]
        key = await self._conversation_key()
        messages: list[MessageRecord] = []
        for message_id in message_ids:
            blob = await self._storage.get(message_path(session_id, message_id))
            data = envelope.unseal(key, f"mysti:message:{session_id}:{message_id}".encode(), blob)[
                0
            ]
            payload = json.loads(data)
            messages.append(
                MessageRecord(
                    id=message_id,
                    session_id=session_id,
                    role=payload["role"],
                    content=payload["content"],
                    timestamp=payload["timestamp"],
                )
            )
        return messages

    async def build_context(self, session_id: str, max_tokens: int = 4096) -> list[dict[str, str]]:
        """Build an LLM context from the most recent messages within a token budget.

        Tokens are approximated as ``len(content) // 4`` characters.
        """
        messages = await self.get_messages(session_id, limit=10**9)
        budget = max_tokens * 4
        selected: list[MessageRecord] = []
        used = 0
        for message in reversed(messages):
            cost = len(message.content)
            if selected and used + cost > budget:
                break
            selected.append(message)
            used += cost
        selected.reverse()
        return [{"role": message.role, "content": message.content} for message in selected]

    async def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """Return recent sessions, most recent first."""
        sessions = await self._load_sessions()
        infos = [
            SessionInfo(
                session_id=session_id,
                created_at=data["created_at"],
                last_at=data["last_at"],
                message_count=data["message_count"],
            )
            for session_id, data in sessions.items()
        ]
        infos.sort(key=lambda info: info.last_at, reverse=True)
        return infos[:limit]

    async def session_exists(self, session_id: str) -> bool:
        """Return True if the session id is known."""
        return session_id in await self._load_sessions()

    async def count_sessions(self) -> int:
        """Return the total number of sessions."""
        return len(await self._load_sessions())
