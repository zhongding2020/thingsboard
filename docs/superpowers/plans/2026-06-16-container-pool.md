# Container Pool Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single opencode Docker container with a managed pool (5-20 containers) that isolates user sessions by container, routing via a new `/api/opencode/*` proxy in the FastAPI backend.

**Architecture:** New `container_pool/` Python module (manager, schemas, proxy, routes) follows existing Proxy + Lifespan patterns. Backend manages Docker containers via `docker-py`, forward requests through httpx. Frontend adds `X-User` header and changes Vite proxy target.

**Tech Stack:** Python 3.11, FastAPI, docker-py, httpx, asyncio, TypeScript, Vue 3, Element Plus

---

### Task 1: Add docker-py dependency

**Files:**
- Modify: `pyproject.toml:9-24`

- [ ] **Step 1: Add `docker` to dependencies list**

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "pydantic",
    "pydantic-settings",
    "asyncpg",
    "nats-py",
    "scipy",
    "scikit-learn",
    "statsmodels",
    "pandas",
    "httpx",
    "click",
    "openpyxl",
    "python-multipart",
    "docker>=7.0.0",
]
```

- [ ] **Step 2: Install the new dependency**

Run: `pip install "docker>=7.0.0"`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add docker-py dependency"
```

---

### Task 2: Add container pool settings

**Files:**
- Modify: `src/process_opt/common/settings.py:1-12`

- [ ] **Step 1: Add pool configuration fields to Settings**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROCESS_OPT_")

    gateway_api_key: str = "dev-api-key"
    nats_url: str = "nats://localhost:4222"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/process_opt"
    nats_stream: str = "PROCESS_OPT"
    process_subject: str = "process_data"
    inspection_subject: str = "inspection_data"

    # Container pool settings
    pool_min_size: int = 5
    pool_max_size: int = 20
    pool_image: str = "opencode-web"
    pool_base_port: int = 5101
    pool_network: str = "thingsboard_default"
    session_ttl_seconds: int = 1800
    health_check_interval_seconds: int = 30
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/common/settings.py
git commit -m "feat: add container pool settings to Settings"
```

---

### Task 3: Create Pydantic schemas for container pool

**Files:**
- Create: `src/process_opt/container_pool/__init__.py`
- Create: `src/process_opt/container_pool/schemas.py`

- [ ] **Step 1: Create `__init__.py`**

```python
```

- [ ] **Step 2: Create `schemas.py`**

```python
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


class SessionState:
    """Internal session→container mapping."""

    def __init__(self, session_id: str, container_id: str, user: str) -> None:
        self.session_id = session_id
        self.container_id = container_id
        self.user = user
        self.last_active: float = 0.0
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/container_pool/__init__.py src/process_opt/container_pool/schemas.py
git commit -m "feat: add container pool schemas"
```

---

### Task 4: Implement ContainerPoolManager

**Files:**
- Create: `src/process_opt/container_pool/manager.py`

- [ ] **Step 1: Write the manager class**

```python
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
        # opencode returns top-level role sometimes; ensure parts exist
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
        # Wait briefly for the container to start
        await asyncio.sleep(2)
        logger.info("Spawned new container %s on port %d", name, port)
        return cs

    async def _health_check_loop(self) -> None:
        while self._running:
            for cs in list(self._containers.values()):
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"http://localhost:{cs.port}/health")
                    if resp.status_code == 200:
                        cs.last_health = time.monotonic()
                        if cs.status == "dead":
                            cs.status = "idle"
                            logger.info("Container %s recovered", cs.name)
                    else:
                        self._mark_dead(cs)
                except Exception:
                    self._mark_dead(cs)
            await asyncio.sleep(self._settings.health_check_interval_seconds)

    async def _recycle_loop(self) -> None:
        while self._running:
            now = time.monotonic()
            # expire stale sessions
            expired_ids = [
                sid
                for sid, ss in self._sessions.items()
                if now - ss.last_active > self._settings.session_ttl_seconds
            ]
            for sid in expired_ids:
                await self.delete_session(sid)
                logger.info("Expired session %s", sid)

            # drain idle containers (those with no sessions) if above min
            busy_ids = {ss.container_id for ss in self._sessions.values()}
            for cs in list(self._containers.values()):
                if cs.status in ("idle", "busy") and cs.container_id not in busy_ids:
                    if cs.status == "busy":
                        cs.status = "draining"
                    elif cs.status == "idle" and len(self._containers) > self._settings.pool_min_size:
                        cs.status = "draining"

            # remove draining containers
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
        # schedule replacement
        asyncio.create_task(self._replace_container(cs))

    async def _replace_container(self, cs: ContainerState) -> None:
        # stop dead container
        try:
            c = self._docker_client.containers.get(cs.container_id)
            await asyncio.to_thread(c.stop, timeout=5)
        except Exception:
            pass
        # remove sessions bound to this container
        for sid, ss in list(self._sessions.items()):
            if ss.container_id == cs.container_id:
                del self._sessions[sid]
        self._containers.pop(cs.container_id, None)
        # spawn replacement
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
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/container_pool/manager.py
git commit -m "feat: implement ContainerPoolManager"
```

---

### Task 5: Create ContainerPoolProxy

**Files:**
- Create: `src/process_opt/container_pool/proxy.py`

- [ ] **Step 1: Write the proxy class**

```python
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

    async def get_messages(self, session_id: str) -> list[Message]:
        return await self._mgr.get_messages(session_id)

    async def list_user_sessions(self, user: str) -> list[Session]:
        return await self._mgr.list_user_sessions(user)

    async def delete_session(self, session_id: str) -> None:
        await self._mgr.delete_session(session_id)
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/container_pool/proxy.py
git commit -m "feat: add ContainerPoolProxy"
```

---

### Task 6: Create FastAPI routes for container pool

**Files:**
- Create: `src/process_opt/container_pool/routes.py`

- [ ] **Step 1: Write routes module**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/container_pool/routes.py
git commit -m "feat: add container pool FastAPI routes"
```

---

### Task 7: Register container pool routes in api/app.py

**Files:**
- Modify: `src/process_opt/api/app.py:118-123`

- [ ] **Step 1: Add ContainerPoolProxy parameter to create_app**

```python
def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisService | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
    container_pool: "ContainerPoolProxy | None" = None,  # <-- new
) -> FastAPI:
```

- [ ] **Step 2: Add TYPE_CHECKING import at top of file**

After the existing imports in `app.py`, add:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from process_opt.container_pool.proxy import ContainerPoolProxy
```

- [ ] **Step 3: Add route registration block before the SPA catch-all**

After the `if analysis_service is not None:` block (around line 565) and before the SPA section (around line 575), add:

```python
    if container_pool is not None:
        from process_opt.container_pool.routes import register_routes as register_pool_routes
        register_pool_routes(app, container_pool)
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/api/app.py
git commit -m "feat: register container pool routes in app factory"
```

---

### Task 8: Wire container pool in api/main.py lifespan

**Files:**
- Modify: `src/process_opt/api/main.py:202-243`

- [ ] **Step 1: Import ContainerPoolProxy and ContainerPoolManager**

Add after the existing imports in `main.py`:

```python
from process_opt.container_pool.manager import ContainerPoolManager
from process_opt.container_pool.proxy import ContainerPoolProxy
```

- [ ] **Step 2: Create proxy and wire it in lifespan**

In `create_api_app_from_settings()`, add the proxy creation:

```python
def create_api_app_from_settings() -> FastAPI:
    settings = Settings()
    repository_proxy = RepositoryProxy()
    parameter_service_proxy = ParameterServiceProxy()
    analysis_service_proxy = AnalysisServiceProxy()
    line_device_repo_proxy = LineDeviceRepositoryProxy()
    container_pool_proxy = ContainerPoolProxy()  # <-- new

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = await create_pool(settings.postgres_dsn)
        migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "db" / "migrations"
        for fpath in sorted(migrations_dir.glob("*.sql")):
            await apply_sql_file(pool, fpath)
        repository = DataRepository(pool)
        line_device_repo = LineDeviceRepository(pool)
        parameter_repo = ParameterRepository(pool)
        parameter_service = ParameterService(parameter_repo)
        dataset_builder = DatasetBuilder(pool)
        analysis_service = AnalysisService(dataset_builder)
        app.state.pool = pool
        app.state.repository = repository
        repository_proxy.repository = repository
        line_device_repo_proxy._repo = line_device_repo
        parameter_service_proxy._service = parameter_service
        analysis_service_proxy._service = analysis_service

        # Container pool initialization
        manager = ContainerPoolManager(settings)
        container_pool_proxy.set_manager(manager)
        await manager.start()

        try:
            yield
        finally:
            await manager.stop()
            container_pool_proxy.reset()
            repository_proxy.repository = None
            line_device_repo_proxy._repo = None
            parameter_service_proxy._service = None
            analysis_service_proxy._service = None
            await pool.close()

    app = create_app(
        repository=repository_proxy,
        parameter_service=parameter_service_proxy,
        analysis_service=analysis_service_proxy,
        line_device_repo=line_device_repo_proxy,
        container_pool=container_pool_proxy,  # <-- new
    )
    app.router.lifespan_context = lifespan
    return app
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/api/main.py
git commit -m "feat: wire container pool in lifespan"
```

---

### Task 9: Add X-User header to frontend API client

**Files:**
- Modify: `web/src/api/opencode.ts:1-49`

- [ ] **Step 1: Add getCurrentUser import and usage**

```typescript
import { useSessionStore } from '@/stores/session'

const API_URL = import.meta.env.DEV ? '/opencode' : 'http://localhost:8000/api/opencode'

function getCurrentUser(): string {
  const store = useSessionStore()
  return store.currentUser || 'anonymous'
}

interface OpencodeSession {
  id: string
  title?: string
}

interface OpencodeMessage {
  id?: string
  info?: { role: string }
  role?: string
  parts: { type: string; text?: string }[]
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'X-User': getCurrentUser(),
      ...opts?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    let detail = `${res.status} ${res.statusText}`
    try {
      const json = JSON.parse(body)
      detail = json.detail || detail
    } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export async function listSessions(): Promise<OpencodeSession[]> {
  return request<OpencodeSession[]>('/session')
}

export async function createSession(): Promise<OpencodeSession> {
  return request<OpencodeSession>('/session', {
    method: 'POST',
    body: JSON.stringify({ title: '工厂分析' }),
  })
}

export async function sendPrompt(sessionId: string, text: string): Promise<OpencodeMessage> {
  return request<OpencodeMessage>(`/session/${encodeURIComponent(sessionId)}/message`, {
    method: 'POST',
    body: JSON.stringify({
      parts: [{ type: 'text', text }],
    }),
  })
}

export async function getMessages(sessionId: string): Promise<OpencodeMessage[]> {
  return request<OpencodeMessage[]>(`/session/${encodeURIComponent(sessionId)}/message`)
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/opencode.ts
git commit -m "feat: add X-User header to opencode API client"
```

---

### Task 10: Update Vite proxy target

**Files:**
- Modify: `web/vite.config.ts:18-22`

- [ ] **Step 1: Change proxy target to backend**

```typescript
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/opencode': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 2: Commit**

```bash
git add web/vite.config.ts
git commit -m "fix: route opencode proxy through backend"
```

---

### Task 11: Remove single opencode container from docker-compose

**Files:**
- Modify: `docker-compose.yml:66-73`

- [ ] **Step 1: Remove the opencode-web service block**

Remove these lines:

```yaml
  opencode-web:
    build: docker/opencode-web
    restart: unless-stopped
    ports:
      - "127.0.0.1:5100:5097"
    environment:
      OPENCODE_WEB_PORT: "5097"
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: remove single opencode container from compose"
```

---

### Task 12: Build and rebuild opencode-web image

**Files:**
- Modify: `docker/opencode-web/Dockerfile` (already updated with Python, verify)

- [ ] **Step 1: Verify Dockerfile has Python installed**

Current expected content:

```dockerfile
FROM node:20-slim

ENV NODE_ENV=production

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv \
      build-essential libpython3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g opencode-ai@latest \
    && npm cache clean --force

EXPOSE 5097

CMD ["opencode", "web", "--port", "5097", "--hostname", "0.0.0.0"]
```

- [ ] **Step 2: Rebuild the image**

Run: `docker build -t opencode-web docker/opencode-web`

- [ ] **Step 3: Commit**

```bash
git add docker/opencode-web/Dockerfile
git commit -m "feat: add Python runtime to opencode image"
```

---

### Task 13: Add health endpoint to opencode image

**Files:**
- Modify: `docker/opencode-web/Dockerfile` (already done)
- Create: `docker/opencode-web/health.js`

**Actually** — opencode CLI's `web` command might not have a built-in `/health` endpoint. We need to verify and possibly add a sidecar.

- [ ] **Step 1: Check if `opencode web` has a `/health` endpoint by examining CLI help**

Run: `docker exec <running-opencode-container> opencode web --help`

If no health endpoint, create a tiny sidecar:

```javascript
// docker/opencode-web/health.js — NOT created yet, check first
```

**Decision**: If opencode web has no `/health`, skip health check loop and use simple TCP port probe instead. Replace `_health_check_loop` in manager.py to use socket connect instead of HTTP.

- [ ] **Step 2: If no HTTP health endpoint, update manager health check**

In `manager.py`, change `_health_check_loop` to use TCP probe:

```python
async def _health_check_loop(self) -> None:
    import socket
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
```

- [ ] **Step 3: Commit** (only if changes needed)

```bash
# If TCP probe change:
git add src/process_opt/container_pool/manager.py
git commit -m "fix: use TCP probe for container health check"
```

---

### Task 14: Integration test — verify pool startup

**Files:**
- Create: `tests/container_pool/__init__.py`
- Create: `tests/container_pool/test_manager.py`

- [ ] **Step 1: Write integration test**

```python
import pytest

from process_opt.common.settings import Settings
from process_opt.container_pool.manager import ContainerPoolManager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pool_start_and_stop():
    """Verify pool starts min containers and stops cleanly."""
    settings = Settings(
        **{
            "PROCESS_OPT_POOL_MIN_SIZE": "2",
            "PROCESS_OPT_POOL_MAX_SIZE": "4",
        }
    )
    manager = ContainerPoolManager(settings)
    try:
        await manager.start()
        assert len(manager._containers) >= 2
    finally:
        await manager.stop()
        assert len(manager._containers) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_session():
    """Verify session creation returns valid session ID."""
    settings = Settings(
        **{
            "PROCESS_OPT_POOL_MIN_SIZE": "1",
            "PROCESS_OPT_POOL_MAX_SIZE": "4",
        }
    )
    manager = ContainerPoolManager(settings)
    try:
        await manager.start()
        session = await manager.create_session("test-user")
        assert session.id
        assert len(session.id) > 0
    finally:
        await manager.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_send_prompt_and_get_messages():
    """Verify end-to-end prompt/message flow."""
    settings = Settings(
        **{
            "PROCESS_OPT_POOL_MIN_SIZE": "1",
            "PROCESS_OPT_POOL_MAX_SIZE": "4",
        }
    )
    manager = ContainerPoolManager(settings)
    try:
        await manager.start()
        session = await manager.create_session("test-user")
        prompt_body = {"parts": [{"type": "text", "text": "Hello"}]}
        response = await manager.forward_message(session.id, prompt_body)
        assert response.parts is not None
        messages = await manager.get_messages(session.id)
        assert len(messages) >= 1
    finally:
        await manager.stop()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/container_pool/test_manager.py -v -m integration`
Expected: 3 PASS (requires Docker daemon running and opencode-web image built)

- [ ] **Step 3: Commit**

```bash
git add tests/container_pool/
git commit -m "test: add container pool integration tests"
```

---

### Task 15: End-to-end smoke test

- [ ] **Step 1: Start the full stack**

Run: `docker-compose up -d` (the backend-api will now start the container pool on boot)

- [ ] **Step 2: Start frontend dev server**

Run: `cd web && npm run dev`

- [ ] **Step 3: Verify the flow**

1. Open `http://localhost:5173` in browser
2. Log in with any username
3. Click the floating AI button → sidebar opens
4. Send a message: "你好"
5. Verify response appears in chat
6. Send another message: "列出设备"
7. Verify multi-turn conversation works

- [ ] **Step 4: Check container pool status** (optional)

Run: `docker ps --filter "name=opencode-pool-" --format "{{.Names}} {{.Ports}}"`

Expected: 5 containers running on ports 5101-5105

---

## Spec Coverage Check

| Spec Requirement | Task(s) |
|-----------------|---------|
| Container pool manager with docker-py | Task 4 |
| Pool settings (min/max size, image, ports) | Task 2 |
| Session→container binding (memory) | Task 4 (create_session, _sessions) |
| Allocation strategy (reuse/idle/expand/503) | Task 4 (_acquire_container) |
| Container state machine (idle/busy/draining/dead) | Task 4 (ContainerState) |
| Health check loop | Task 4 + Task 13 |
| Idle session recycling (30 min TTL) | Task 4 (_recycle_loop) |
| Proxy pattern for DI | Task 5 |
| FastAPI route registration /api/opencode/* | Task 6 |
| Conditional route registration in app.py | Task 7 |
| Lifespan wiring in main.py | Task 8 |
| Frontend X-User header | Task 9 |
| Vite proxy → backend | Task 10 |
| Remove single opencode from compose | Task 11 |
| Docker image with Python | Task 12 |
| Health endpoint or TCP probe | Task 13 |
| Integration tests | Task 14 |
| End-to-end smoke test | Task 15 |
