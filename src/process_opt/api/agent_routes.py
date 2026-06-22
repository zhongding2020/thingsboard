"""Agent API routes — DeepAgents backend.

Replaces the old LangGraph StateGraph SSE layer. The public API surface
(POST /session, POST /chat, GET /chat/{id}/events, GET /session/{id}/messages,
GET /processes, POST /upload) is unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from langchain_core.messages import AIMessageChunk
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

# In-memory session store (replaces SessionManager + AgentSession)
_sessions: dict[str, dict[str, Any]] = {}


def register_agent_routes(
    app: Any,
    agent_factory: Any,        # async callable(llm, process_type) -> DeepAgent
    llm: Any = None,
) -> None:
    """Register agent routes on the FastAPI app.

    Args:
        app: FastAPI application instance.
        agent_factory: Async callable that returns a DeepAgent for a process type.
        llm: Chat model (used for suggestions, etc.).
    """
    router = APIRouter(prefix="/api/v1/agent")

    # --- Background session expiry ---
    _expiry_started = False

    async def _ensure_expiry():
        nonlocal _expiry_started
        if _expiry_started:
            return
        _expiry_started = True
        asyncio.create_task(_expire_stale(ttl=1800))

    async def _expire_stale(ttl: int = 1800):
        while True:
            await asyncio.sleep(300)
            now = time.monotonic()
            expired = [
                sid for sid, s in _sessions.items()
                if now - s.get("created", now) > ttl
            ]
            for sid in expired:
                del _sessions[sid]
                logger.debug("Expired session %s", sid)

    # --- Routes ---

    @router.post("/session")
    async def create_session(request: Request) -> dict:
        await _ensure_expiry()
        user = request.headers.get("X-User", "anonymous")
        body = await request.json()
        process_type = body.get("process_type", "adhesive_curing")

        agent = await agent_factory(llm, process_type)
        sid = f"ses_{uuid.uuid4().hex[:20]}"
        thread_id = f"thread_{uuid.uuid4().hex[:20]}"
        _sessions[sid] = {
            "agent": agent,
            "thread_id": thread_id,
            "user": user,
            "process_type": process_type,
            "messages": [],
            "created": time.monotonic(),
        }
        return {"session_id": sid, "process_type": process_type}

    @router.get("/session")
    async def list_sessions(request: Request) -> list[dict]:
        user = request.headers.get("X-User", "anonymous")
        return [
            {
                "session_id": sid,
                "process_type": s["process_type"],
                "message_count": len(s.get("messages", [])),
            }
            for sid, s in _sessions.items()
            if s.get("user") == user
        ]

    @router.post("/chat")
    async def send_message(request: Request) -> Response:
        body = await request.json()
        session_id = body.get("session_id", "")
        text = body.get("text", "")
        if not session_id or not text:
            raise HTTPException(status_code=400, detail="session_id and text required")

        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话已过期，请重新开始")

        session["messages"].append({"role": "user", "content": text})
        session["pending"] = True
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/chat/{session_id}/events")
    async def stream_events(session_id: str) -> StreamingResponse:
        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.pop("pending", False):
            # No pending message — return immediately
            async def empty():
                yield b'data: {"type":"session.status","status":"idle"}\n\n'
            return StreamingResponse(empty(), media_type="text/event-stream")

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in session["messages"]
        ]

        async def generate():
            try:
                async for event in session["agent"].astream_events(
                    {"messages": messages},
                    config={"configurable": {"thread_id": session["thread_id"]}},
                    version="v2",
                ):
                    sse = _map_event(event)
                    if sse:
                        yield sse

                # Emit suggestions
                if llm is not None and session.get("messages"):
                    suggestions = await _generate_suggestions(
                        llm,
                        [{"role": m["role"], "content": m["content"]}
                         for m in session["messages"]],
                    )
                    yield f'data: {{"type":"suggestions","questions":{json.dumps(suggestions)}}}\n\n'.encode()

                yield b'data: {"type":"session.status","status":"idle"}\n\n'
            except GeneratorExit:
                logger.debug("SSE client disconnected for session %s", session_id)
            except Exception as exc:
                logger.error("SSE stream error for session %s: %s", session_id, exc)
                err = json.dumps({"type": "error", "message": str(exc)})
                yield f"data: {err}\n\n".encode()
                yield b'data: {"type":"session.status","status":"idle"}\n\n'

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
        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.get("messages", [])

    @router.get("/processes")
    async def list_processes() -> list[dict]:
        from process_opt.agent.skills import discover_skills, get_process_skills
        registry = discover_skills()
        return [
            {"process_type": s["name"], "display_name": s.get("display_name", s["name"])}
            for s in get_process_skills(registry)
        ]

    @router.post("/upload")
    async def upload_dataset_route(file: UploadFile) -> dict:
        from process_opt.analysis.excel import parse_excel, save_dataset

        if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls / .csv 文件")

        content = await file.read()
        ds = parse_excel(content)
        ds_id = save_dataset(ds)
        feature_fields = sorted({k for f in ds.features for k in f})
        target_fields = sorted({k for t in ds.targets for k in t})
        return {
            "dataset_id": ds_id,
            "fields": {"features": feature_fields, "targets": target_fields},
            "sample_count": ds.sample_count,
        }

    app.include_router(router)


def _map_event(event: dict) -> bytes | None:
    """Map DeepAgents astream_events event to SSE bytes.

    Keeps the same SSE event type names as the old LangGraph layer
    so the frontend needs zero changes.
    """
    kind = event.get("event", "")

    # AI text streaming
    if kind == "on_chat_model_stream":
        chunk: Any = event.get("data", {}).get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            text = chunk.content
            if isinstance(text, list):
                text = "".join(str(t) for t in text)
            data = json.dumps({"type": "message.delta", "text": str(text)})
            return f"data: {data}\n\n".encode()

    # Tool start
    if kind == "on_tool_start":
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})
        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        data = json.dumps({"type": "tool.call", "name": name, "args": args}, default=str)
        return f"data: {data}\n\n".encode()

    # Tool end
    if kind == "on_tool_end":
        output = event.get("data", {}).get("output", "")
        if hasattr(output, "content"):
            output_str = str(output.content)
        else:
            output_str = str(output)
        data = json.dumps({"type": "tool.result", "name": event.get("name", ""),
                           "data": output_str})
        return f"data: {data}\n\n".encode()

    # Subagent start (maps to old node.start)
    if kind == "on_chain_start":
        name = event.get("name", "")
        data = json.dumps({"type": "node.start", "node": name})
        return f"data: {data}\n\n".encode()

    # Subagent end (maps to old node.end)
    if kind == "on_chain_end":
        name = event.get("name", "")
        data = json.dumps({"type": "node.end", "node": name})
        return f"data: {data}\n\n".encode()

    return None


async def _generate_suggestions(llm: Any, messages: list[dict]) -> list[str]:
    """Generate follow-up question suggestions from conversation context."""
    from langchain_core.messages import SystemMessage

    context = ""
    for msg in messages[-6:]:  # last 6 messages only
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        context += f"[{msg.get('role', 'unknown')}]: {str(content)[:300]}\n"

    prompt = (
        "基于以下对话，生成3个用户可能继续提问的简短问题。\n"
        "问题要具体、与工艺分析相关，用中文。\n"
        "只输出问题列表，每行一个，不要序号和标记。\n\n"
        f"{context}"
    )
    try:
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        lines = [
            l.strip("- 1234567890. ")
            for l in (response.content or "").strip().split("\n")
            if l.strip()
        ]
        return [l for l in lines if len(l) > 3][:3]
    except Exception:
        return []
