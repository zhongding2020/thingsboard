"""Agent chat routes — Vercel AI SDK v5 UI Message Stream Protocol.

Single endpoint:
    POST /api/chat
        Request:  { messages: UIMessage[], processType?: str, sessionId?: str }
        Response: text/event-stream (UI Message Stream v1)

Design:
    - Stateless per-request; frontend sends full message history each time
    - Session ID maps 1:1 to LangGraph thread_id (checkpointer continuity)
    - Process type auto-inferred from first user message on session creation
    - Agent cache keyed by (sessionId, processType) so we don't rebuild every request
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from process_opt.api import ui_stream
from process_opt.api.langgraph_to_ui import stream_langgraph_as_ui

logger = logging.getLogger(__name__)


# Simple in-process agent cache. Keyed by sessionId. Value is (agent, thread_id, process_type).
# LangGraph checkpointer handles per-thread state; we just avoid rebuilding the agent object.
_agent_cache: dict[str, tuple[Any, str, str]] = {}


class UIMessagePart(BaseModel):
    """Vercel AI SDK v5 UIMessage part.

    We only care about `type` and `text` here; other part types (tool-*, data-*)
    are ignored on the way in because history reconstruction only needs text.
    """
    type: str
    text: str | None = None


class UIMessage(BaseModel):
    """Vercel AI SDK v5 UIMessage."""
    id: str | None = None
    role: str  # 'user' | 'assistant' | 'system'
    parts: list[UIMessagePart] = Field(default_factory=list)
    # v5 removed content field; v4 back-compat:
    content: str | None = None


class ChatRequest(BaseModel):
    messages: list[UIMessage]
    processType: str = "adhesive_curing"
    sessionId: str | None = None


def register_agent_routes(
    app: Any,
    agent_factory: Any,      # async (llm, process_type) -> DeepAgent
    llm: Any = None,         # unused; kept for signature compatibility
) -> None:
    router = APIRouter(prefix="/api")

    @router.post("/chat")
    async def chat(request: Request) -> StreamingResponse:
        body = await request.json()
        try:
            req = ChatRequest(**body)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid request: {exc}")

        if not req.messages:
            raise HTTPException(status_code=422, detail="messages must not be empty")

        session_id = req.sessionId or f"ses_{uuid.uuid4().hex[:20]}"
        process_type = req.processType

        # Reuse cached agent if same session + process type
        cache_key = session_id
        cached = _agent_cache.get(cache_key)
        if cached and cached[2] == process_type:
            agent, thread_id, _ = cached
        else:
            try:
                agent = await agent_factory(llm, process_type)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            thread_id = f"thread_{uuid.uuid4().hex[:20]}"
            _agent_cache[cache_key] = (agent, thread_id, process_type)

        # Convert UIMessage[] → LangGraph messages format
        lg_messages = [_ui_message_to_langgraph(m) for m in req.messages]

        return StreamingResponse(
            stream_langgraph_as_ui(agent, lg_messages, thread_id),
            headers=ui_stream.SSE_HEADERS,
        )

    app.include_router(router)


def _ui_message_to_langgraph(msg: UIMessage) -> dict[str, str]:
    """Extract text content from a UIMessage for LangGraph consumption.

    LangGraph agent expects `{"role": ..., "content": str}`. We concatenate
    all `text` parts. For assistant messages, tool interaction parts are
    dropped — the agent's checkpointer already knows about them via thread_id.
    """
    if msg.parts:
        text_pieces = [p.text or "" for p in msg.parts if p.type == "text"]
        content = "".join(text_pieces)
    else:
        content = msg.content or ""
    return {"role": msg.role, "content": content}
