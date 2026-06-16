# Container Pool Manager — 设计文档

## 目标

为 opencode 会话实现用户级容器隔离，支撑 500 用户规模。替换当前单容器架构为容器池架构。

## 架构

```
前端 (Vue)
  │  POST /session          GET /session/{id}/message
  ▼
Vite Proxy: /opencode → localhost:8000/api/opencode
  │
  ▼
FastAPI Backend (localhost:8000)  ← 新增 /api/opencode/* 路由
  │
  │ ContainerPoolManager (新增模块)
  │   ├─ docker-py 管理容器生命周期
  │   ├─ 内存维护 sessionId → container 映射
  │   └─ 后台任务：健康检查 + 空闲回收
  │
  ▼
Docker 容器池 (端口 5101-5120)
  ├─ opencode-pool-1  :5101
  ├─ opencode-pool-2  :5102
  ├─ ...
  └─ opencode-pool-20 :5120
```

## 新增模块：`src/process_opt/container_pool/`

### 文件结构

```
container_pool/
├── __init__.py
├── manager.py        # ContainerPoolManager — 核心池管理
├── proxy.py          # ContainerPoolProxy — 按 Proxy 模式延迟初始化
├── schemas.py        # Pydantic 请求/响应模型
└── routes.py         # FastAPI 路由处理函数
```

### ContainerPoolManager (`manager.py`)

**职责**：管理容器池的创建、分配、回收、健康检查。

**接口**：

```python
class ContainerPoolManager:
    def __init__(self, settings: Settings):
        """
        从 Settings 读取:
        - pool_min_size: int = 5      # 最小容器数
        - pool_max_size: int = 50     # 最大容器数
        - pool_image: str             # opencode 镜像名
        - pool_base_port: int = 5101  # 起始端口
        - session_ttl_seconds: int = 1800  # 30分钟空闲过期
        - health_interval_seconds: int = 30
        """

    async def start(self) -> None:
        """启动最小数量的容器，开始后台健康检查任务"""

    async def stop(self) -> None:
        """停止所有容器，取消后台任务"""

    async def create_session(self, user: str) -> Session:
        """分配容器，创建 session，返回 sessionId"""

    async def forward_message(self, session_id: str, body: dict) -> Message:
        """将 prompt 转发到 session 所在容器，返回响应"""

    async def get_messages(self, session_id: str) -> list[Message]:
        """获取 session 的历史消息"""

    async def list_user_sessions(self, user: str) -> list[Session]:
        """列出用户的 session 列表"""
```

**内部状态**（内存）：

```python
# 容器池
containers: dict[str, ContainerState]  # container_id → ContainerState

# Session 映射
sessions: dict[str, SessionState]      # session_id → SessionState

@dataclass
class ContainerState:
    container: Container              # docker-py Container 对象
    port: int                         # 宿主机端口
    status: Literal["idle", "busy", "draining", "dead"]
    last_health: float                # monotic time
    async_lock: asyncio.Lock          # 分配/回收时的并发锁

@dataclass
class SessionState:
    session_id: str                   # opencode 原生 session id
    container_id: str                 # 绑定容器的 id
    user: str                         # 用户名
    last_active: float                # monotic time
```

### 容器状态机

```
              创建 session            session 结束 / 过期回收
  [idle] ──────────────────→ [busy] ──────────────────→ [draining]
                                                              │
                                              清理完成           │ 超时 5s
     ┌────────────────────────────────────────←───┘              │
     ▼                                                           ▼
  [idle]                                                  [dead] ──→ 销毁重建

  [idle/busy] ── 健康检查失败 ──→ [dead] ──→ 销毁 ──→ 重建
```

### 分配策略

1. 先查找是否有该用户已有 session 的容器 → 复用该容器
2. 若无，找状态为 `idle` 且空闲最久的容器
3. 若 idle 为空且容器数 < pool_max_size → 启动新容器分配
4. 若已达 pool_max_size → 返回 HTTP 503 + "系统繁忙，请稍后重试"

### 分配流程（并发安全）

```python
async def _acquire_container(self, user: str) -> ContainerState:
    async with self._pool_lock:
        # 1. 尝试复用该用户已有容器
        for c in self.containers.values():
            if c.status == "busy" and any(s.user == user for s in self.sessions.values() if s.container_id == c.id):
                # 找到该用户活跃的 session 所在容器
                ...
        # 2. 找空闲容器
        idle = sorted([c for c in self.containers.values() if c.status == "idle"],
                      key=lambda c: c.last_allocated)
        if idle:
            ...
        # 3. 扩容
        if len(self.containers) < self.pool_max_size:
            ...
        # 4. 已满
        raise ContainerPoolFullError()
```

### 空闲回收

后台 `asyncio.Task`，每 60 秒执行：

1. 遍历所有 session，标记 `last_active > session_ttl` 的为过期
2. 检查每个 busy 容器是否还有活跃 session
3. 无活跃 session 的容器进入 draining 状态
4. draining 容器：调用 opencode 的 session 清理（或直接重建容器）

### 健康检查

后台 `asyncio.Task`，每 30 秒执行：

```python
async def _health_check_loop(self):
    while self._running:
        for c in list(self.containers.values()):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"http://localhost:{c.port}/health", timeout=5.0)
                if resp.status_code == 200:
                    c.last_health = time.monotonic()
                    if c.status == "dead":
                        c.status = "idle"  # 恢复了
                else:
                    self._mark_dead(c)
            except Exception:
                self._mark_dead(c)

        # 替换 dead 容器
        for c in [c for c in self.containers.values() if c.status == "dead"]:
            await self._replace_container(c)

        await asyncio.sleep(30)
```

### Proxy 模式 (`proxy.py`)

```python
class ContainerPoolProxy:
    """遵循现有 RepositoryProxy 模式"""

    def __init__(self):
        self._manager: ContainerPoolManager | None = None

    def set_manager(self, manager: ContainerPoolManager):
        self._manager = manager

    def reset(self):
        self._manager = None

    # 代理所有方法: create_session / forward_message / get_messages / list_user_sessions
```

### 路由注册 (`routes.py`)

```python
def register_routes(app: FastAPI, pool: ContainerPoolProxy):
    router = APIRouter(prefix="/api/opencode")

    @router.post("/session")
    async def create_session(request: Request, body: dict):
        user = request.headers.get("X-User", "anonymous")
        session = await pool._manager.create_session(user)
        return session

    @router.post("/session/{session_id}/message")
    async def send_message(session_id: str, body: dict):
        return await pool._manager.forward_message(session_id, body)

    @router.get("/session/{session_id}/message")
    async def get_messages(session_id: str):
        return await pool._manager.get_messages(session_id)

    @router.get("/session")
    async def list_sessions(request: Request):
        user = request.headers.get("X-User", "anonymous")
        return await pool._manager.list_user_sessions(user)

    app.include_router(router)
```

### 在 `api/app.py` 中注册

```python
def create_app(..., container_pool: ContainerPoolProxy | None = None):
    ...
    if container_pool is not None:
        register_routes(app, container_pool)
    ...
```

### 在 `api/main.py` lifespan 中初始化

```python
async def lifespan(app: FastAPI):
    pool_proxy = ContainerPoolProxy()
    try:
        # ... 现有初始化 ...
        manager = ContainerPoolManager(settings)
        pool_proxy.set_manager(manager)
        await manager.start()
        app.state.container_pool = pool_proxy
        yield
    finally:
        await manager.stop()
        pool_proxy.reset()
```

## 前端改动

### API 客户端 (`opencode.ts`)

无需改动 API 接口形状，只需添加 `X-User` 请求头：

```typescript
// 在 request() 函数中添加 header
headers: {
  'Content-Type': 'application/json',
  'X-User': getCurrentUser(),  // 从 session store 获取
  ...opts?.headers,
},
```

### Vite Proxy

proxy 目标从直接连容器改为连后端：

```typescript
'/opencode': {
  target: 'http://localhost:8000',  // 改为连后端
  changeOrigin: true,
  // 不再需要 rewrite，后端路由匹配 /api/opencode/*
}
```

## Docker Compose 改动

移除单个 `opencode-web` 服务，替换为池启动脚本：

```yaml
# docker-compose.yml 中移除 opencode-web 服务
# 容器池由 ContainerPoolManager 在运行时通过 docker-py 动态管理
```

容器通过 docker-py 动态创建：

```python
container = docker_client.containers.run(
    image=settings.pool_image,
    detach=True,
    ports={f"5097/tcp": port},  # 容器内 5097 → 宿主机 port
    name=f"opencode-pool-{index}",
    environment={"NODE_ENV": "production"},
    network="thingsboard_default",  # 与后端同网络
)
```

## 依赖新增

`pyproject.toml` 添加：

```toml
"docker>=7.0.0",  # docker-py (Docker SDK for Python)
```

## 错误处理

| 场景 | HTTP 状态码 | 错误信息 |
|------|-----------|---------|
| 池已满无空闲容器 | 503 | 系统繁忙，请稍后重试 |
| 容器健康检查失败（自动恢复中） | 503 | 服务暂时不可用，正在恢复 |
| session 已过期 | 404 | 会话已过期，请重新开始 |
| Docker daemon 不可达 | 500 | 容器管理服务异常 |

## 测试策略

- **单元测试**：mock docker-py，测试分配/回收/过期逻辑
- **集成测试**：用真实 Docker socket 启动少量容器，测试完整请求链路
- **压力测试**：模拟 50+ 并发用户，验证容器自动扩缩容
