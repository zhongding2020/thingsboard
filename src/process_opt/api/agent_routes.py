from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from langchain_core.messages import AIMessageChunk
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

_tool_start_times: dict[str, float] = {}
_supervisor_text: str = ""


def register_agent_routes(
    app: Any,
    session_manager: Any,
    knowledge_loader: Any,
    graph: Any,
    llm: Any = None,
) -> None:
    router = APIRouter(prefix="/api/v1/agent")

    @router.post("/session")
    async def create_session(request: Request) -> dict:
        user = request.headers.get("X-User", "anonymous")
        body = await request.json()
        process_type = body.get("process_type", "adhesive_curing")
        session = await session_manager.create(user, process_type, graph, llm=llm)
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
                        if llm is not None and session.state.get("messages"):
                            suggestions = await _generate_suggestions(llm, session.state["messages"])
                            yield f'data: {{"type":"suggestions","questions":{json.dumps(suggestions)}}}\n\n'.encode()
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
    global _supervisor_text

    kind = event.get("event", "")

    if kind == "on_chat_model_stream":
        node_name = event.get("metadata", {}).get("langgraph_node", "")
        chunk: Any = event.get("data", {}).get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            text = chunk.content
            if isinstance(text, list):
                text = "".join(str(t) for t in text)
            if node_name == "supervisor":
                global _supervisor_text
                _supervisor_text += str(text)
                return None
            data = json.dumps({"type": "message.delta", "text": str(text)})
            return f"data: {data}\n\n".encode()

    if kind == "on_chain_end":
        node_name = event.get("name", "")
        if node_name == "supervisor":
            result_parts: list[bytes] = []

            # Phase change event
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict):
                phase = output.get("phase", "")
                phase_action = output.get("phase_action", "")
                prev_phase = output.get("prev_phase", "")
                if phase_action in ("ADVANCE", "BACK") and phase:
                    data = json.dumps({
                        "type": "phase.change",
                        "phase": phase,
                        "prev_phase": prev_phase,
                        "action": phase_action,
                    })
                    result_parts.append(f"data: {data}\n\n".encode())

            if _supervisor_text.strip():
                data = json.dumps({"type": "agent.trace", "node": "supervisor", "text": _supervisor_text.strip()})
                _supervisor_text = ""
                result_parts.append(f"data: {data}\n\n".encode())

            if result_parts:
                return b"".join(result_parts)
            return None
        if node_name in ("chat", "analyzer", "recommender"):
            data = json.dumps({"type": "node.end", "node": node_name})
            return f"data: {data}\n\n".encode()

    if kind == "on_tool_start":
        run_id = event.get("run_id", "")
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})
        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        _tool_start_times[run_id] = time.time()
        data = json.dumps({"type": "tool.call", "name": name, "args": args, "run_id": run_id}, default=str)
        return f"data: {data}\n\n".encode()

    if kind == "on_tool_end":
        run_id = event.get("run_id", "")
        name = event.get("name", "")
        output = event.get("data", {}).get("output", "")
        start_time = _tool_start_times.pop(run_id, None)
        duration_ms = round((time.time() - start_time) * 1000) if start_time else 0
        # Extract content: ToolMessage object → .content, else str
        if hasattr(output, 'content'):
            output_str = str(output.content)
        else:
            output_str = str(output)
        data = json.dumps({"type": "tool.result", "name": name, "data": output_str, "run_id": run_id, "duration_ms": duration_ms})
        return f"data: {data}\n\n".encode()

    if kind == "on_chain_start":
        node_name = event.get("name", "")
        if node_name in ("chat", "analyzer", "recommender"):
            data = json.dumps({"type": "node.start", "node": node_name})
            return f"data: {data}\n\n".encode()

    return None


async def _generate_suggestions(llm: Any, messages: list) -> list[str]:
    from langchain_core.messages import SystemMessage

    context = ""
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        context += f"[{role}]: {str(content)[:300]}\n"

    prompt = (
        "基于以下对话，生成3个用户可能继续提问的简短问题。\n"
        "问题要具体、与工艺分析相关，用中文。\n"
        "只输出问题列表，每行一个，不要序号和标记。\n\n"
        f"{context}"
    )
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    lines = [l.strip("- 1234567890. ") for l in (response.content or "").strip().split("\n") if l.strip()]
    return [l for l in lines if len(l) > 3][:3]
