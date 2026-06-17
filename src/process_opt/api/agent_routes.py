from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from langchain_core.messages import AIMessageChunk
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


def register_agent_routes(
    app: Any,
    session_manager: Any,
    knowledge_loader: Any,
    graph: Any,
) -> None:
    router = APIRouter(prefix="/api/v1/agent")

    @router.post("/session")
    async def create_session(request: Request) -> dict:
        user = request.headers.get("X-User", "anonymous")
        body = await request.json()
        process_type = body.get("process_type", "adhesive_curing")
        session = await session_manager.create(user, process_type, graph)
        return {"session_id": session.session_id, "process_type": process_type}

    @router.get("/session")
    async def list_sessions(request: Request) -> list[dict]:
        user = request.headers.get("X-User", "anonymous")
        return await session_manager.list_user(user)

    @router.post("/chat")
    async def send_message(request: Request) -> Response:
        body = await request.json()
        session_id = body.get("session_id", "")
        text = body.get("text", "")
        if not session_id or not text:
            raise HTTPException(status_code=400, detail="session_id and text required")
        session = await session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话已过期，请重新开始")
        await session.send_message(text)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/chat/{session_id}/events")
    async def stream_events(session_id: str) -> StreamingResponse:
        session = await session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        async def generate():
            try:
                while True:
                    event = await session.event_queue.get()
                    if event.get("type") == "done":
                        yield b'data: {"type":"session.status","status":"idle"}\n\n'
                        break
                    if event.get("type") == "error":
                        err = json.dumps({"type":"error","message":event["message"]})
                        yield f"data: {err}\n\n".encode()
                        yield b'data: {"type":"session.status","status":"idle"}\n\n'
                        break
                    sse = _map_event(event)
                    if sse:
                        yield sse
            except Exception as e:
                logger.error("SSE stream error: %s", e)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/session/{session_id}/messages")
    async def get_messages(session_id: str) -> list[dict]:
        session = await session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.get_messages()

    @router.get("/processes")
    async def list_processes() -> list[dict]:
        return knowledge_loader.list_processes()

    app.include_router(router)


def _map_event(event: dict) -> bytes | None:
    kind = event.get("event", "")

    if kind == "on_chat_model_stream":
        chunk: Any = event.get("data", {}).get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            text = chunk.content
            if isinstance(text, list):
                text = "".join(str(t) for t in text)
            data = json.dumps({"type": "message.delta", "text": str(text)})
            return f"data: {data}\n\n".encode()

    if kind == "on_tool_start":
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})
        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        data = json.dumps({"type": "tool.call", "name": name, "args": args}, default=str)
        return f"data: {data}\n\n".encode()

    if kind == "on_tool_end":
        name = event.get("name", "")
        output = event.get("data", {}).get("output", "")
        data = json.dumps({"type": "tool.result", "name": name, "data": str(output)})
        return f"data: {data}\n\n".encode()

    if kind == "on_chain_start":
        node_name = event.get("name", "")
        if node_name in ("chat", "analyzer", "recommender"):
            data = json.dumps({"type": "node.start", "node": node_name})
            return f"data: {data}\n\n".encode()

    if kind == "on_chain_end":
        node_name = event.get("name", "")
        if node_name in ("chat", "analyzer", "recommender"):
            data = json.dumps({"type": "node.end", "node": node_name})
            return f"data: {data}\n\n".encode()

    return None
