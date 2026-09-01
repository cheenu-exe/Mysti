"""FastAPI application exposing the Phase 0 Memory Service API.

Binds to localhost by default. When MYSTI_API_TOKEN is set, every route except
/health requires a Bearer token (protects against other local processes and
DNS-rebinding).
"""

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from mysti.core.context import AppContext
from mysti.exceptions import LLMError, MystiError, RecordNotFoundError
from mysti.memory.models import MemoryRecord, SearchHit

_SYSTEM_PROMPT = (
    "You are MYSTI, the user's private AI assistant. "
    "You can remember and recall information the user stores, and you remember "
    "context from earlier in this conversation. "
    "You cannot access the user's system (Passive Mode). "
    "Be helpful, direct, and slightly technical. Ask for clarification when needed."
)


class StoreRequest(BaseModel):
    category: str
    content: str
    metadata: dict = Field(default_factory=dict)


class StoreResponse(BaseModel):
    id: str
    created_at: str


class SearchRequest(BaseModel):
    query: str
    category: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    results: list[SearchHit]


class DeleteResponse(BaseModel):
    id: str
    deleted: bool


class CategoriesResponse(BaseModel):
    categories: dict[str, int]


class StartResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    content: str


class MessagesResponse(BaseModel):
    messages: list


class HealthResponse(BaseModel):
    status: str
    storage: str
    encryption: bool


class StatusResponse(BaseModel):
    mode: str
    memory_records: int
    conversations: int
    cache_entries: int


def create_app(ctx: AppContext) -> FastAPI:
    """Build the FastAPI application around an initialized AppContext."""
    app = FastAPI(title="MYSTI Memory Service", version="0.1.0")

    async def require_token(authorization: str | None = Header(default=None)) -> None:
        token = ctx.settings.api_token
        if token is None:
            return
        if authorization != f"Bearer {token}":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing bearer token"
            )

    @app.exception_handler(RecordNotFoundError)
    async def _not_found(_request: Request, exc: RecordNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MystiError)
    async def _mysti_error(_request: Request, exc: MystiError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(LLMError)
    async def _llm_error(_request: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", storage=ctx.settings.storage_provider, encryption=True)

    @app.get("/status", response_model=StatusResponse, dependencies=[Depends(require_token)])
    async def system_status() -> StatusResponse:
        return StatusResponse(
            mode="passive",
            memory_records=await ctx.memory.count_records(),
            conversations=await ctx.conversations.count_sessions(),
            cache_entries=ctx.cache.stats()["entries"],
        )

    @app.post("/memory/store", response_model=StoreResponse, dependencies=[Depends(require_token)])
    async def memory_store(body: StoreRequest) -> StoreResponse:
        record = await ctx.memory.store(body.category, body.content, body.metadata)
        return StoreResponse(id=record.id, created_at=record.created_at)

    @app.get(
        "/memory/retrieve/{record_id}",
        response_model=MemoryRecord,
        dependencies=[Depends(require_token)],
    )
    async def memory_retrieve(record_id: str) -> MemoryRecord:
        return await ctx.memory.retrieve(record_id)

    @app.post(
        "/memory/search", response_model=SearchResponse, dependencies=[Depends(require_token)]
    )
    async def memory_search(body: SearchRequest) -> SearchResponse:
        return SearchResponse(
            results=await ctx.memory.search(body.query, body.category, body.limit)
        )

    @app.delete("/memory/{record_id}", response_model=DeleteResponse)
    async def memory_delete(record_id: str) -> DeleteResponse:
        await ctx.memory.delete(record_id)
        return DeleteResponse(id=record_id, deleted=True)

    @app.get(
        "/memory/categories",
        response_model=CategoriesResponse,
        dependencies=[Depends(require_token)],
    )
    async def memory_categories() -> CategoriesResponse:
        return CategoriesResponse(categories=await ctx.memory.list_categories())

    @app.post(
        "/conversation/start", response_model=StartResponse, dependencies=[Depends(require_token)]
    )
    async def conversation_start() -> StartResponse:
        return StartResponse(session_id=await ctx.conversations.start_session())

    @app.post("/conversation/{session_id}/message", dependencies=[Depends(require_token)])
    async def conversation_message(session_id: str, body: MessageRequest) -> dict:
        if not await ctx.conversations.session_exists(session_id):
            raise HTTPException(status_code=404, detail="conversation session not found")
        user_message = await ctx.conversations.add_message(session_id, "user", body.content)
        history = await ctx.conversations.build_context(session_id)
        reply = await ctx.llm.complete([{"role": "system", "content": _SYSTEM_PROMPT}, *history])
        assistant_message = await ctx.conversations.add_message(session_id, "assistant", reply)
        return {"user_message": user_message, "response": assistant_message}

    @app.get(
        "/conversation/{session_id}/messages",
        response_model=MessagesResponse,
        dependencies=[Depends(require_token)],
    )
    async def conversation_messages(
        session_id: str, limit: int = 50, offset: int = 0
    ) -> MessagesResponse:
        messages = await ctx.conversations.get_messages(session_id, limit=limit, offset=offset)
        return MessagesResponse(messages=messages)

    return app
