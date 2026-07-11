"""UI Message Stream Protocol encoder (Vercel AI SDK v5).

Emits `data: <json>\\n\\n` SSE chunks conforming to the AI SDK UI Message
Stream v1 wire format. Each helper returns bytes ready to be yielded from
a FastAPI StreamingResponse.

Wire format reference:
    Response header: Content-Type: text/event-stream, x-vercel-ai-ui-message-stream: v1
    Each chunk:      data: <json>\\n\\n
    Terminator:      data: [DONE]\\n\\n

Chunk types we emit:
    start                 { type, messageId }
    start-step            { type }
    text-start            { type, id }
    text-delta            { type, id, delta }
    text-end              { type, id }
    tool-input-start      { type, toolCallId, toolName }
    tool-input-available  { type, toolCallId, toolName, input }
    tool-output-available { type, toolCallId, output }
    tool-output-error     { type, toolCallId, errorText }
    finish-step           { type }
    finish                { type }
    error                 { type, errorText }
    data-<name>           { type, id?, data }
"""

from __future__ import annotations

import json
from typing import Any


def _encode(payload: dict[str, Any]) -> bytes:
    """Encode a chunk dict as SSE bytes."""
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n".encode()


def start(message_id: str) -> bytes:
    return _encode({"type": "start", "messageId": message_id})


def start_step() -> bytes:
    return _encode({"type": "start-step"})


def text_start(part_id: str) -> bytes:
    return _encode({"type": "text-start", "id": part_id})


def text_delta(part_id: str, delta: str) -> bytes:
    return _encode({"type": "text-delta", "id": part_id, "delta": delta})


def text_end(part_id: str) -> bytes:
    return _encode({"type": "text-end", "id": part_id})


def tool_input_start(tool_call_id: str, tool_name: str) -> bytes:
    return _encode({
        "type": "tool-input-start",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
    })


def tool_input_available(tool_call_id: str, tool_name: str, tool_input: Any) -> bytes:
    return _encode({
        "type": "tool-input-available",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "input": tool_input,
    })


def tool_output_available(tool_call_id: str, output: Any) -> bytes:
    return _encode({
        "type": "tool-output-available",
        "toolCallId": tool_call_id,
        "output": output,
    })


def tool_output_error(tool_call_id: str, error_text: str) -> bytes:
    return _encode({
        "type": "tool-output-error",
        "toolCallId": tool_call_id,
        "errorText": error_text,
    })


def finish_step() -> bytes:
    return _encode({"type": "finish-step"})


def finish() -> bytes:
    return _encode({"type": "finish"})


def error(error_text: str) -> bytes:
    return _encode({"type": "error", "errorText": error_text})


def data_part(name: str, data: Any, part_id: str | None = None) -> bytes:
    """Custom data-* part. Frontend renders as `part.type === 'data-<name>'`."""
    payload: dict[str, Any] = {"type": f"data-{name}", "data": data}
    if part_id:
        payload["id"] = part_id
    return _encode(payload)


def done() -> bytes:
    """Terminator per AI SDK spec."""
    return b"data: [DONE]\n\n"


SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "x-vercel-ai-ui-message-stream": "v1",
}
