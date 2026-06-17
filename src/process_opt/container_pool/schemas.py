from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    model_config = {"extra": "allow"}
    title: str | None = None
    cwd: str | None = None


class Session(BaseModel):
    id: str
    title: str | None = None


class MessagePart(BaseModel):
    type: str
    text: str | None = None


class Message(BaseModel):
    id: str | None = None
    info: dict[str, Any] | None = None
    role: str | None = None
    parts: list[MessagePart] = Field(default_factory=list)


class PromptRequest(BaseModel):
    parts: list[MessagePart] = Field(default_factory=list)


class ContainerState:
    """Internal state tracking (not a Pydantic model)."""

    def __init__(self, container_id: str, port: int, name: str) -> None:
        self.container_id = container_id
        self.port = port
        self.name = name
        self.status: Literal["idle", "busy", "draining", "dead"] = "idle"
        self.last_health: float = 0.0
        self.last_allocated: float = 0.0
        self._fail_count: int = 0


class SessionState:
    """Internal session→container mapping."""

    def __init__(self, session_id: str, container_id: str, user: str) -> None:
        self.session_id = session_id
        self.container_id = container_id
        self.user = user
        self.last_active: float = 0.0
