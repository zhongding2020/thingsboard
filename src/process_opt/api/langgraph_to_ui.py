"""Convert LangGraph astream_events (v2) to Vercel AI SDK UI Message Stream.

Consumes DeepAgents / LangGraph events and yields SSE chunks in the
Vercel AI SDK v5 wire format. Zero business logic — pure protocol translation.

Design decisions:
    - Subagent chain events are treated as regular assistant text (no subagent UI)
    - Reasoning parts are not emitted (project uses non-thinking models)
    - Todos and suggestions are not emitted (features cut per redesign)
    - Tool inputs are emitted once at on_tool_start (no streaming delta of args)
    - Tool ID from LangGraph run_id (16-char prefix) for stable frontend keys
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessageChunk

from process_opt.api import ui_stream

logger = logging.getLogger(__name__)


async def stream_langgraph_as_ui(
    agent: Any,
    messages: list[dict[str, str]],
    thread_id: str,
) -> AsyncIterator[bytes]:
    """Drive `agent.astream_events(v2)` and emit UI Message Stream chunks.

    Args:
        agent: DeepAgent instance (has `astream_events()` method).
        messages: History as `[{"role": "user"|"assistant", "content": str}, ...]`.
        thread_id: LangGraph checkpointer thread id for state continuity.
    """
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    text_part_id: str | None = None
    open_tool_calls: set[str] = set()

    yield ui_stream.start(message_id)
    yield ui_stream.start_step()

    stream_config = {"configurable": {"thread_id": thread_id}}

    try:
        async for event in agent.astream_events(
            {"messages": messages},
            config=stream_config,
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk_data: Any = event.get("data", {}).get("chunk")
                if not isinstance(chunk_data, AIMessageChunk):
                    continue
                text = chunk_data.content
                if isinstance(text, list):
                    text = "".join(str(t) for t in text)
                text = str(text or "")
                if not text:
                    continue
                if text_part_id is None:
                    text_part_id = f"text_{uuid.uuid4().hex[:12]}"
                    yield ui_stream.text_start(text_part_id)
                yield ui_stream.text_delta(text_part_id, text)
                continue

            if kind == "on_tool_start":
                if text_part_id:
                    yield ui_stream.text_end(text_part_id)
                    text_part_id = None

                tool_name = event.get("name", "unknown")
                run_id = event.get("run_id", "")
                tool_call_id = _tool_call_id(run_id)
                tool_input = event.get("data", {}).get("input", {}) or {}
                cleaned_input = {k: v for k, v in tool_input.items() if not k.startswith("_")}

                open_tool_calls.add(tool_call_id)
                yield ui_stream.tool_input_start(tool_call_id, tool_name)
                yield ui_stream.tool_input_available(tool_call_id, tool_name, cleaned_input)
                continue

            if kind == "on_tool_end":
                run_id = event.get("run_id", "")
                tool_call_id = _tool_call_id(run_id)
                output = event.get("data", {}).get("output", "")
                if hasattr(output, "content"):
                    output_str = str(output.content)
                else:
                    output_str = str(output)
                open_tool_calls.discard(tool_call_id)
                yield ui_stream.tool_output_available(tool_call_id, output_str)
                continue

            # Chain start/end are ignored — subagent UI is intentionally removed

    except Exception as exc:
        logger.error("LangGraph stream error: %s", exc, exc_info=True)
        if text_part_id:
            yield ui_stream.text_end(text_part_id)
            text_part_id = None
        for tid in list(open_tool_calls):
            yield ui_stream.tool_output_error(tid, str(exc))
        yield ui_stream.error(str(exc))
    finally:
        if text_part_id:
            yield ui_stream.text_end(text_part_id)
        yield ui_stream.finish_step()
        yield ui_stream.finish()
        yield ui_stream.done()


def _tool_call_id(run_id: str) -> str:
    """Derive a stable toolCallId from LangGraph run_id."""
    return f"call_{run_id[:16]}" if run_id else f"call_{uuid.uuid4().hex[:16]}"
