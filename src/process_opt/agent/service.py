from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from process_opt.agent.schemas import AgentChatRequest


class AgentService(Protocol):
    async def chat(self, request: AgentChatRequest) -> AsyncIterator[str]: ...


class OpenAIAgentService:
    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def chat(self, request: AgentChatRequest) -> AsyncIterator[str]:
        from process_opt.agent.executor import run_agent

        async for chunk in run_agent(
            request.message,
            self.api_key,
            self.model,
            self.base_url,
        ):
            yield chunk
