from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from process_opt.container_pool.manager import ContainerPoolFullError
from process_opt.container_pool.proxy import ContainerPoolProxy


def register_routes(app: Any, pool_proxy: ContainerPoolProxy) -> None:
    router = APIRouter(prefix="/api/opencode")

    @router.post("/session")
    async def create_session(request: Request) -> Any:
        user = request.headers.get("X-User", "anonymous")
        try:
            session = await pool_proxy.create_session(user)
            return session.model_dump()
        except ContainerPoolFullError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )

    @router.post("/session/{session_id}/message")
    async def send_message(session_id: str, body: dict[str, Any]) -> Any:
        try:
            msg = await pool_proxy.forward_message(session_id, body)
            return msg.model_dump()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"请求失败: {e}",
            )

    @router.get("/session/{session_id}/message")
    async def get_messages(session_id: str) -> Any:
        try:
            msgs = await pool_proxy.get_messages(session_id)
            return [m.model_dump() for m in msgs]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"获取消息失败: {e}",
            )

    @router.get("/session")
    async def list_sessions(request: Request) -> Any:
        user = request.headers.get("X-User", "anonymous")
        try:
            sessions = await pool_proxy.list_user_sessions(user)
            return [s.model_dump() for s in sessions]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"获取会话列表失败: {e}",
            )

    @router.delete("/session/{session_id}")
    async def delete_session(session_id: str) -> Response:
        try:
            await pool_proxy.delete_session(session_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"删除失败: {e}",
            )

    app.include_router(router)
