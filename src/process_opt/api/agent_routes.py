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
        action_responses = body.get("action_responses") or []

        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        if not text and not action_responses:
            raise HTTPException(status_code=400, detail="text or action_responses required")

        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话已过期，请重新开始")

        # Build user message content
        content_parts: list[str] = []
        if text:
            content_parts.append(text)
        if action_responses:
            for ar in action_responses:
                action_id = ar.get("action_id", "")
                value = ar.get("value", {})
                content_parts.append(f"[交互响应 action_id={action_id}]: {json.dumps(value, ensure_ascii=False)}")
        content = "\n".join(content_parts)

        session["messages"].append({"role": "user", "content": content})
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
            subagent_run_ids: set[str] = set()
            stream_config = {"configurable": {"thread_id": session["thread_id"]}}
            try:
                async for event in session["agent"].astream_events(
                    {"messages": messages},
                    config=stream_config,
                    version="v2",
                ):
                    sse = _map_event(event, subagent_run_ids)
                    if sse:
                        yield sse

                    # Emit todo.update after tool_end events
                    if event.get("event") == "on_tool_end":
                        try:
                            state = await session["agent"].aget_state(stream_config)
                            raw_todos = state.values.get("todos", [])
                            normalized = _normalize_todos(raw_todos)
                            todo_data = json.dumps({"type": "todo.update", "todos": normalized})
                            yield f"data: {todo_data}\n\n".encode()
                        except Exception:
                            pass

                # Emit final todo.update at stream end
                try:
                    state = await session["agent"].aget_state(stream_config)
                    raw_todos = state.values.get("todos", [])
                    normalized = _normalize_todos(raw_todos)
                    todo_data = json.dumps({"type": "todo.update", "todos": normalized})
                    yield f"data: {todo_data}\n\n".encode()
                except Exception:
                    pass

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
                logger.error("Traceback:", exc_info=True)
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
        ds_id = await save_dataset(ds)
        feature_fields = sorted({k for f in ds.features for k in f})
        target_fields = sorted({k for t in ds.targets for k in t})
        return {
            "dataset_id": ds_id,
            "fields": {"features": feature_fields, "targets": target_fields},
            "sample_count": ds.sample_count,
        }

    app.include_router(router)


def _normalize_todos(raw_todos: list[dict]) -> list[dict]:
    """Map DeepAgents todo format {content, status} → frontend format {id, text, done}."""
    normalized = []
    for i, t in enumerate(raw_todos or []):
        status = t.get("status", "pending")
        normalized.append({
            "id": t.get("id", f"todo_{i}"),
            "text": t.get("content", t.get("text", "")),
            "done": status in ("completed", "done"),
        })
    return normalized


def _map_event(event: dict, subagent_run_ids: set[str] | None = None) -> bytes | None:
    """Map DeepAgents astream_events event to SSE bytes.

    Keeps the same SSE event type names as the old LangGraph layer
    so the frontend needs zero changes.

    New in v2: differentiates subagent events (subagent.start, subagent.delta,
    subagent.end) from root agent events (node.start, message.delta, node.end)
    by tracking subagent chain run IDs.
    """
    kind = event.get("event", "")

    # Determine if this event is inside a subagent context
    parent_id = event.get("parent_run_id", "")
    inside_subagent = bool(subagent_run_ids and parent_id in subagent_run_ids)

    # AI text streaming
    if kind == "on_chat_model_stream":
        chunk: Any = event.get("data", {}).get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            text = chunk.content
            if isinstance(text, list):
                text = "".join(str(t) for t in text)
            event_type = "subagent.delta" if inside_subagent else "message.delta"
            data = json.dumps({"type": event_type, "text": str(text)})
            return f"data: {data}\n\n".encode()

    # Tool start
    if kind == "on_tool_start":
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})

        # ask_user is intercepted — emit interactive.prompt instead of tool.call
        if name == "ask_user":
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action_data: dict[str, Any] = {"id": action_id}
            # Copy scalar fields with camelCase key mapping
            for src, dst in (("type", "type"), ("title", "title"),
                             ("description", "description"), ("placeholder", "placeholder")):
                if inp.get(src):
                    action_data[dst] = inp[src]
            if inp.get("confirm_text"):
                action_data["confirmText"] = inp["confirm_text"]
            if inp.get("cancel_text"):
                action_data["cancelText"] = inp["cancel_text"]
            # Parse JSON string fields to objects
            for src, dst in (("options", "options"), ("cascader_levels", "cascaderLevels")):
                raw = inp.get(src, "")
                if raw and raw != "[]":
                    try:
                        action_data[dst] = json.loads(raw) if isinstance(raw, str) else raw
                    except (json.JSONDecodeError, TypeError):
                        pass
            if inp.get("default_value") and inp["default_value"]:
                try:
                    action_data["defaultValue"] = json.loads(inp["default_value"]) if isinstance(inp["default_value"], str) else inp["default_value"]
                except (json.JSONDecodeError, TypeError):
                    pass
            data = json.dumps({"type": "interactive.prompt", "action": action_data}, default=str)
            return f"data: {data}\n\n".encode()

        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        data = json.dumps({"type": "tool.call", "name": name, "args": args}, default=str)
        return f"data: {data}\n\n".encode()

    # Tool end
    if kind == "on_tool_end":
        # Skip tool.result for ask_user — already handled as interactive.prompt
        if event.get("name", "") == "ask_user":
            return None
        output = event.get("data", {}).get("output", "")
        if hasattr(output, "content"):
            output_str = str(output.content)
        else:
            output_str = str(output)
        data = json.dumps({"type": "tool.result", "name": event.get("name", ""),
                           "data": output_str})
        return f"data: {data}\n\n".encode()

    # Chain start — differentiate subagent vs node
    if kind == "on_chain_start":
        name = event.get("name", "")
        tags = event.get("tags", [])
        run_id = event.get("run_id", "")

        is_subagent = _is_subagent_event(name, tags)
        if is_subagent and subagent_run_ids is not None:
            subagent_run_ids.add(run_id)

        event_type = "subagent.start" if is_subagent else "node.start"
        data = json.dumps({"type": event_type, "node": name})
        return f"data: {data}\n\n".encode()

    # Chain end — differentiate subagent vs node
    if kind == "on_chain_end":
        name = event.get("name", "")
        run_id = event.get("run_id", "")

        is_subagent_end = bool(subagent_run_ids and run_id in subagent_run_ids)
        if is_subagent_end and subagent_run_ids is not None:
            subagent_run_ids.discard(run_id)

        event_type = "subagent.end" if is_subagent_end else "node.end"
        data = json.dumps({"type": event_type, "node": name})
        return f"data: {data}\n\n".encode()

    return None


def _is_subagent_event(name: str, tags: list) -> bool:
    """Detect if a chain event belongs to a subagent.

    Checks the chain name and tags for subagent indicators.
    DeepAgents subagent spawns create nested chains whose names
    contain ``subagent`` or tags include ``subagent``.
    """
    name_lower = name.lower()
    if "subagent" in name_lower or "sub_agent" in name_lower:
        return True
    for tag in tags:
        if "subagent" in str(tag).lower():
            return True
    return False


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
