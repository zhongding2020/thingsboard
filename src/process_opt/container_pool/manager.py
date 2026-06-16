import asyncio
import logging
import time
from typing import Any

import httpx

from process_opt.common.settings import Settings
from process_opt.container_pool.schemas import (
    ContainerState,
    Message,
    PromptRequest,
    Session,
    SessionCreateRequest,
    SessionState,
)

logger = logging.getLogger(__name__)


class ContainerPoolFullError(Exception):
    pass


class ContainerPoolManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._containers: dict[str, ContainerState] = {}
        self._sessions: dict[str, SessionState] = {}
        self._pool_lock = asyncio.Lock()
        self._running = False
        self._health_task: asyncio.Task[None] | None = None
        self._recycle_task: asyncio.Task[None] | None = None
        self._next_port = settings.pool_base_port

    async def start(self) -> None:
        import docker

        try:
            self._docker_client = docker.DockerClient.from_env()
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Docker daemon: {e}") from e

        for i in range(self._settings.pool_min_size):
            port = self._next_port
            self._next_port += 1
            name = f"opencode-pool-{i + 1}"
            container = self._docker_client.containers.run(
                image=self._settings.pool_image,
                detach=True,
                ports={f"5097/tcp": port},
                name=name,
                environment={"NODE_ENV": "production"},
                network=self._settings.pool_network,
                remove=True,
            )
            self._containers[container.id] = ContainerState(
                container_id=container.id, port=port, name=name
            )
            logger.info("Started container %s on port %d", name, port)

        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        self._recycle_task = asyncio.create_task(self._recycle_loop())
        logger.info("Container pool started with %d containers", len(self._containers))

    async def stop(self) -> None:
        self._running = False
        if self._health_task:
            self._health_task.cancel()
        if self._recycle_task:
            self._recycle_task.cancel()
        tasks = []
        for cs in list(self._containers.values()):
            try:
                c = self._docker_client.containers.get(cs.container_id)
                tasks.append(asyncio.to_thread(c.stop, timeout=5))
            except Exception:
                pass
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._containers.clear()
        self._sessions.clear()
        logger.info("Container pool stopped")

    async def create_session(self, user: str) -> Session:
        cs = await self._acquire_container(user)
        url = f"http://localhost:{cs.port}/session"
        body = SessionCreateRequest(title=f"{user}-工厂分析", cwd=f"/workspace/user-{user}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body.model_dump(exclude_none=True))
            resp.raise_for_status()
            data = resp.json()
        session_id = data["id"]
        self._sessions[session_id] = SessionState(
            session_id=session_id,
            container_id=cs.container_id,
            user=user,
        )
        self._sessions[session_id].last_active = time.monotonic()
        cs.last_allocated = time.monotonic()
        return Session(id=session_id, title=data.get("title"))

    async def forward_message(self, session_id: str, body: dict[str, Any]) -> Message:
        ss = self._get_session_or_raise(session_id)
        cs = self._containers[ss.container_id]
        url = f"http://localhost:{cs.port}/session/{session_id}/message"
        ss.last_active = time.monotonic()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        if "parts" not in data:
            data = {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": str(data)}]}
        return Message(**data)

    async def get_messages(self, session_id: str) -> list[Message]:
        ss = self._get_session_or_raise(session_id)
        cs = self._containers[ss.container_id]
        url = f"http://localhost:{cs.port}/session/{session_id}/message"
        ss.last_active = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, list):
            return [Message(**m) for m in data]
        return []

    async def list_user_sessions(self, user: str) -> list[Session]:
        results: list[Session] = []
        for ss in self._sessions.values():
            if ss.user != user:
                continue
            cs = self._containers.get(ss.container_id)
            if cs is None:
                continue
            url = f"http://localhost:{cs.port}/session"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("id") == ss.session_id:
                                results.append(Session(id=item["id"], title=item.get("title")))
                ss.last_active = time.monotonic()
            except Exception:
                pass
        return results

    async def delete_session(self, session_id: str) -> None:
        ss = self._sessions.pop(session_id, None)
        if ss is None:
            return
        cs = self._containers.get(ss.container_id)
        if cs is None:
            return
        url = f"http://localhost:{cs.port}/session/{session_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(url)
        except Exception:
            pass

    # ── internal helpers ──────────────────────────────────────────

    def _get_session_or_raise(self, session_id: str) -> SessionState:
        ss = self._sessions.get(session_id)
        if ss is None:
            from fastapi import HTTPException
            from fastapi import status as http_status

            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="会话已过期，请重新开始",
            )
        return ss

    async def _acquire_container(self, user: str) -> ContainerState:
        async with self._pool_lock:
            # 1. reuse existing container for this user
            for ss in self._sessions.values():
                if ss.user == user:
                    cs = self._containers.get(ss.container_id)
                    if cs and cs.status == "busy":
                        return cs

            # 2. find idle container (FIFO)
            idle = sorted(
                [c for c in self._containers.values() if c.status == "idle"],
                key=lambda c: c.last_allocated,
            )
            if idle:
                cs = idle[0]
                cs.status = "busy"
                return cs

            # 3. expand pool
            if len(self._containers) < self._settings.pool_max_size:
                return await self._spawn_container()

            # 4. full
            raise ContainerPoolFullError("系统繁忙，请稍后重试")

    async def _spawn_container(self) -> ContainerState:
        port = self._next_port
        self._next_port += 1
        name = f"opencode-pool-{len(self._containers) + 1}"
        import docker

        client = self._docker_client
        container = await asyncio.to_thread(
            client.containers.run,
            image=self._settings.pool_image,
            detach=True,
            ports={f"5097/tcp": port},
            name=name,
            environment={"NODE_ENV": "production"},
            network=self._settings.pool_network,
            remove=True,
        )
        cs = ContainerState(container_id=container.id, port=port, name=name)
        cs.status = "busy"
        self._containers[container.id] = cs
        await asyncio.sleep(2)
        logger.info("Spawned new container %s on port %d", name, port)
        return cs

    async def _health_check_loop(self) -> None:
        while self._running:
            for cs in list(self._containers.values()):
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection("localhost", cs.port),
                        timeout=5.0,
                    )
                    writer.close()
                    await writer.wait_closed()
                    cs.last_health = time.monotonic()
                    if cs.status == "dead":
                        cs.status = "idle"
                        logger.info("Container %s recovered", cs.name)
                except Exception:
                    self._mark_dead(cs)
            await asyncio.sleep(self._settings.health_check_interval_seconds)

    async def _recycle_loop(self) -> None:
        while self._running:
            now = time.monotonic()
            expired_ids = [
                sid
                for sid, ss in self._sessions.items()
                if now - ss.last_active > self._settings.session_ttl_seconds
            ]
            for sid in expired_ids:
                await self.delete_session(sid)
                logger.info("Expired session %s", sid)

            busy_ids = {ss.container_id for ss in self._sessions.values()}
            for cs in list(self._containers.values()):
                if cs.status in ("idle", "busy") and cs.container_id not in busy_ids:
                    if cs.status == "busy":
                        cs.status = "draining"
                    elif cs.status == "idle" and len(self._containers) > self._settings.pool_min_size:
                        cs.status = "draining"

            for cs in [c for c in self._containers.values() if c.status == "draining"]:
                try:
                    c = self._docker_client.containers.get(cs.container_id)
                    await asyncio.to_thread(c.stop, timeout=5)
                except Exception:
                    pass
                self._containers.pop(cs.container_id, None)
                logger.info("Drained container %s", cs.name)

            await asyncio.sleep(60)

    def _mark_dead(self, cs: ContainerState) -> None:
        if cs.status != "dead":
            logger.warning("Container %s marked dead", cs.name)
            cs.status = "dead"
        asyncio.create_task(self._replace_container(cs))

    async def _replace_container(self, cs: ContainerState) -> None:
        try:
            c = self._docker_client.containers.get(cs.container_id)
            await asyncio.to_thread(c.stop, timeout=5)
        except Exception:
            pass
        for sid, ss in list(self._sessions.items()):
            if ss.container_id == cs.container_id:
                del self._sessions[sid]
        self._containers.pop(cs.container_id, None)
        port = cs.port
        name = cs.name
        try:
            container = await asyncio.to_thread(
                self._docker_client.containers.run,
                image=self._settings.pool_image,
                detach=True,
                ports={f"5097/tcp": port},
                name=name,
                environment={"NODE_ENV": "production"},
                network=self._settings.pool_network,
                remove=True,
            )
            new_cs = ContainerState(container_id=container.id, port=port, name=name)
            new_cs.status = "idle"
            self._containers[container.id] = new_cs
            logger.info("Replaced dead container %s", name)
        except Exception as e:
            logger.error("Failed to replace container %s: %s", name, e)
