from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "tool"
    content: str


class ExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    execution_time: float = 0.0
