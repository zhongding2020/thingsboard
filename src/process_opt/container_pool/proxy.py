from typing import Any

from process_opt.container_pool.schemas import Message, Session


class ContainerPoolProxy:
    """Proxy that defers to ContainerPoolManager, set during lifespan."""

    def __init__(self) -> None:
        self._manager: Any = None

    def set_manager(self, manager: Any) -> None:
        self._manager = manager

    def reset(self) -> None:
        self._manager = None

    @property
    def _mgr(self) -> Any:
        if self._manager is None:
            raise RuntimeError("ContainerPoolManager not initialized")
        return self._manager

    async def create_session(self, user: str) -> Session:
        return await self._mgr.create_session(user)

    async def forward_message(self, session_id: str, body: dict[str, Any]) -> Message:
        return await self._mgr.forward_message(session_id, body)

    async def send_prompt_async(self, session_id: str, body: dict[str, Any]) -> None:
        await self._mgr.send_prompt_async(session_id, body)

    async def stream_events(self, session_id: str):
        async for line in self._mgr.stream_events(session_id):
            yield line

    async def get_messages(self, session_id: str) -> list[Message]:
        return await self._mgr.get_messages(session_id)

    async def list_user_sessions(self, user: str) -> list[Session]:
        return await self._mgr.list_user_sessions(user)

    async def delete_session(self, session_id: str) -> None:
        await self._mgr.delete_session(session_id)
