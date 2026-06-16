# Agent 系统实施计划

> **For agentic workers:** Use superpowers:subagent-driven-development

**目标:** 构建 Code-as-Action 模式的工厂分析 Agent，LLM 动态生成 Python 代码并在沙箱中执行

**架构:** 后端 sandbox + executor (Python) → SSE streaming → 前端 chat UI (Vue + @ai-sdk/vue)

**Tech Stack:** Python FastAPI / subprocess / openai / Vue 3 / @ai-sdk/vue / Element Plus

---

### Task 1: 后端依赖 + 数据模型

**Files:**
- Modify: `pyproject.toml` — 添加 `openai`
- Create: `src/process_opt/agent/schemas.py`

- [ ] **Step 1: 添加依赖**

```toml
# pyproject.toml dependencies 追加
    "openai",
```

安装:
```bash
cd /Users/zhongding/dev/thingsboard && pip install openai
```

- [ ] **Step 2: 创建 schemas.py**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str
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
```

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: agent schemas and openai dependency"
```

---

### Task 2: 代码沙箱

**Files:**
- Create: `src/process_opt/agent/sandbox.py`
- Create: `tests/agent/test_sandbox.py`

- [ ] **Step 1: 写测试**

```python
from __future__ import annotations
import pytest
from process_opt.agent.sandbox import execute_code


class TestExecuteCode:
    def test_simple_expression(self) -> None:
        result = execute_code("print(1 + 1)")
        assert result.success
        assert "2" in result.stdout

    def test_json_output(self) -> None:
        code = """
import json
print(json.dumps({"mean": 5.0, "std": 2.0}))
"""
        result = execute_code(code)
        data = json.loads(result.stdout.strip())
        assert data["mean"] == 5.0

    def test_timeout(self) -> None:
        code = "import time; time.sleep(10)"
        result = execute_code(code, timeout=1)
        assert not result.success
        assert "timed out" in result.error.lower()

    def test_numpy_available(self) -> None:
        code = "import numpy as np; print(np.array([1,2,3]).mean())"
        result = execute_code(code)
        assert result.success
        assert "2.0" in result.stdout
```

- [ ] **Step 2: 实现 sandbox.py**

```python
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from process_opt.agent.schemas import ExecutionResult


def execute_code(
    code: str,
    timeout: int = 30,
    workdir: str | None = None,
) -> ExecutionResult:
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="agent_sandbox_")

    script_path = Path(workdir) / "_agent_script.py"
    script_path.write_text(code, encoding="utf-8")

    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        return ExecutionResult(
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            execution_time=round(elapsed, 3),
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return ExecutionResult(
            success=False,
            error=f"Execution timed out after {timeout}s",
            execution_time=round(elapsed, 3),
        )
    except Exception as e:
        elapsed = time.time() - start
        return ExecutionResult(
            success=False,
            error=str(e),
            execution_time=round(elapsed, 3),
        )
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/zhongding/dev/thingsboard && python3 -m pytest tests/agent/test_sandbox.py -v
```

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: code execution sandbox"
```

---

### Task 3: Agent Executor（LLM 编排）

**Files:**
- Create: `src/process_opt/agent/executor.py`
- Create: `src/process_opt/agent/db.py`

- [ ] **Step 1: 创建 db.py（沙箱内 DB 查询辅助）**

```python
from __future__ import annotations

"""Helper for agent-generated code to query production data.
This module's functions are injected into the sandbox namespace."""


def query(sql: str) -> list[dict]:
    """Execute SQL query against the production database.
    Returns list of dicts (rows).
    """
    import os
    import asyncpg
    import asyncio

    dsn = os.environ.get("PROCESS_OPT_POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/process_opt")

    async def _run():
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(sql)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    return asyncio.run(_run())


def query_analysis_records(
    device_id: str | None = None,
    days: int = 7,
) -> list[dict]:
    """Query recent analysis records for a device."""
    import json

    import httpx

    base_url = os.environ.get("PROCESS_OPT_API_URL", "http://localhost:8000")
    params: dict[str, str | int] = {"page_size": 1000}
    if device_id:
        params["device_id"] = device_id

    resp = httpx.get(f"{base_url}/api/v1/analysis/records", params=params)
    resp.raise_for_status()
    return resp.json()["rows"]
```

- [ ] **Step 2: 实现 executor.py**

```python
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from process_opt.agent.schemas import AgentChatRequest, ExecutionResult
from process_opt.agent.sandbox import execute_code

SYSTEM_PROMPT = """你是一位工厂工艺参数分析专家。你的任务是：
1. 理解用户的分析需求
2. 编写 Python 代码来完成分析
3. 执行代码并解读结果

## 可用库
numpy, scipy, scikit-learn, pandas, statsmodels, json, math

## 数据库查询
```python
from agent_db import query, query_analysis_records
rows = query("SELECT * FROM analysis_records LIMIT 10")
# 或
records = query_analysis_records(device_id="reflow_001")
```

## 代码要求
- 输出结果用 print(json.dumps(...)) 格式
- 图表用 base64 嵌入 JSON
- 代码必须完整、可独立运行
- 每次只生成一个版本的代码

## 输出格式
在 ```python 代码块中提供完整的 Python 脚本。
"""

MAX_RETRIES = 3


def _extract_code(text: str) -> str | None:
    import re
    m = re.search(r"```python\n(.+?)\n```", text, re.DOTALL)
    return m.group(1).strip() if m else None


async def run_agent(
    request: AgentChatRequest,
    api_key: str,
    model: str = "gpt-4o",
) -> AsyncIterator[str]:
    client = AsyncOpenAI(api_key=api_key)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if request.conversation_id:
        # TODO: 加载历史消息
        pass

    messages.append({"role": "user", "content": request.message})
    yield json.dumps({"type": "status", "content": "thinking"}) + "\n"

    for attempt in range(MAX_RETRIES):
        # LLM 生成代码
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        full_response = ""
        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            full_response += content

        # 提取并执行代码
        code = _extract_code(full_response)
        if not code:
            yield json.dumps({"type": "text", "content": full_response}) + "\n"
            return

        yield json.dumps({"type": "code", "content": code}) + "\n"
        yield json.dumps({"type": "status", "content": "executing"}) + "\n"

        result = execute_code(code)

        if result.success:
            # 从 stdout 解析结构化结果
            parsed = None
            for line in result.stdout.strip().split("\n"):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

            # 让 LLM 解读结果
            messages.append({"role": "assistant", "content": full_response})
            messages.append({
                "role": "user",
                "content": f"代码执行成功。stdout:\n{result.stdout}\n\n"
                           f"请用中文解读分析结果，如果有图表数据则描述图表。",
            })
            yield json.dumps({"type": "result", "content": result.stdout[:2000]}) + "\n"

            # 获取解读
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                yield json.dumps({"type": "text", "content": content}) + "\n"
            return

        else:
            # 代码出错，让 LLM 修复
            error_msg = result.stderr or result.error or "Unknown error"
            yield json.dumps({"type": "error", "content": error_msg[:500]}) + "\n"

            messages.append({"role": "assistant", "content": full_response})
            messages.append({
                "role": "user",
                "content": f"代码执行出错:\n{error_msg}\n\n请修正代码后重新输出。",
            })

    yield json.dumps({"type": "status", "content": f"failed after {MAX_RETRIES} attempts"}) + "\n"
```

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: agent executor with LLM code generation"
```

---

### Task 4: AgentService + SSE 端点

**Files:**
- Create: `src/process_opt/agent/service.py`
- Modify: `src/process_opt/api/app.py`
- Modify: `src/process_opt/api/main.py`

- [ ] **Step 1: 创建 service.py**

```python
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Protocol

from process_opt.agent.schemas import AgentChatRequest


class AgentService(Protocol):
    async def chat(self, request: AgentChatRequest) -> AsyncIterator[str]: ...


class OpenAIAgentService:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    async def chat(self, request: AgentChatRequest) -> AsyncIterator[str]:
        from process_opt.agent.executor import run_agent
        async for chunk in run_agent(request, self.api_key, self.model):
            yield chunk
```

- [ ] **Step 2: 在 app.py 中添加 SSE 端点**

在 `if analysis_service is not None:` 块之后（或单独新块）：

```python
from collections.abc import AsyncIterator
from process_opt.agent.schemas import AgentChatRequest


class AgentService(Protocol):
    async def chat(self, request: AgentChatRequest) -> AsyncIterator[str]: ...


# 在 create_app 参数中添加 agent_service
def create_app(
    ...
    agent_service: AgentService | None = None,
) -> FastAPI:
    ...

    if agent_service is not None:

        @app.post("/api/v1/agent/chat")
        async def agent_chat_route(request: AgentChatRequest):
            from fastapi.responses import StreamingResponse

            async def event_stream():
                async for chunk in agent_service.chat(request):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
```

- [ ] **Step 3: 在 main.py 中注入 AgentService**

```python
# 在 lifespan 中初始化
from process_opt.agent.service import OpenAIAgentService
agent_service = OpenAIAgentService(
    api_key=settings.openai_api_key,
    model="gpt-4o",
)

# create_app 时传入
app = create_app(
    ...
    agent_service=agent_service,
)
```

在 settings 中添加 `openai_api_key`:

```python
# common/settings.py
openai_api_key: str = ""
```

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: agent SSE endpoint and service wiring"
```

---

### Task 5: 前端 AI SDK + Agent API

**Files:**
- Modify: `web/package.json` — 添加 `ai`, `@ai-sdk/vue`
- Create: `web/src/api/agent.ts`

- [ ] **Step 1: 安装依赖**

```bash
cd /Users/zhongding/dev/thingsboard/web && npm install ai @ai-sdk/vue
```

- [ ] **Step 2: 创建 agent.ts**

```typescript
import client from './client'

export interface AgentChatRequest {
  message: string
  conversation_id?: string
}

export async function* chatStream(request: AgentChatRequest): AsyncGenerator<string> {
  const response = await fetch('/api/v1/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(request),
  })

  if (!response.ok) throw new Error(`Agent chat failed: ${response.status}`)

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        yield data
      }
    }
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: frontend agent SSE client"
```

---

### Task 6: AgentChat.vue 组件

**Files:**
- Create: `web/src/components/AgentChat.vue`

- [ ] **Step 1: 实现组件**

```vue
<template>
  <div>
    <el-button class="agent-float" circle @click="visible = !visible">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 6v6l4 2"/>
      </svg>
    </el-button>
    <Teleport to="body">
      <Transition name="agent-panel">
        <div v-if="visible" class="agent-panel">
          <div class="agent-header">
            <span>AI 分析助手</span>
            <el-button text size="small" @click="visible = false">✕</el-button>
          </div>
          <div class="agent-messages" ref="msgRef">
            <div v-for="(msg, i) in messages" :key="i" class="agent-msg" :class="msg.role">
              <div v-if="msg.role === 'user'" class="msg-bubble user-msg">{{ msg.content }}</div>
              <div v-else-if="msg.type === 'text'" class="msg-bubble assistant-msg">{{ msg.content }}</div>
              <div v-else-if="msg.type === 'code'" class="msg-code">
                <div class="code-header">
                  <el-icon style="margin-right: 4px;"><Monitor /></el-icon> 生成代码
                  <el-button text size="small" @click="copyCode(msg.content)">复制</el-button>
                </div>
                <pre><code>{{ msg.content }}</code></pre>
              </div>
              <div v-else-if="msg.type === 'error'" class="msg-error">
                <el-icon><WarningFilled /></el-icon> {{ msg.content }}
              </div>
              <div v-else-if="msg.type === 'status'" class="msg-status">
                <el-icon class="is-loading"><Loading /></el-icon> {{ msg.content }}
              </div>
            </div>
            <div v-if="loading" class="agent-msg assistant-msg">
              <span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
          </div>
          <div class="agent-input">
            <el-input
              v-model="input"
              placeholder="输入分析需求..."
              @keyup.enter="send"
              :disabled="loading"
            >
              <template #append>
                <el-button @click="send" :disabled="!input.trim() || loading">发送</el-button>
              </template>
            </el-input>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { chatStream } from '@/api/agent'
import { Monitor, WarningFilled, Loading } from '@element-plus/icons-vue'

const visible = ref(false)
const input = ref('')
const loading = ref(false)
const msgRef = ref<HTMLDivElement>()
const messages = ref<{ role: string; type: string; content: string }[]>([])

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''

  messages.value.push({ role: 'user', type: 'text', content: text })
  loading.value = true
  scrollBottom()

  try {
    const response = await fetch('/api/v1/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message: text }),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') break
        try {
          const parsed = JSON.parse(data)
          messages.value.push({ role: 'assistant', type: parsed.type, content: parsed.content })
          scrollBottom()
        } catch { /* raw text */ }
      }
    }
  } catch (e: any) {
    messages.value.push({ role: 'assistant', type: 'error', content: e.message })
  } finally {
    loading.value = false
    scrollBottom()
  }
}

async function copyCode(code: string) {
  await navigator.clipboard.writeText(code)
}

function scrollBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}
</script>

<style scoped>
.agent-float { /* same as opencode-float */ }

.agent-panel {
  position: fixed; right: 20px; bottom: 72px;
  z-index: 9998; width: 480px; height: 640px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  display: flex; flex-direction: column; overflow: hidden;
}

.agent-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--el-border-color-light);
  font-size: 14px; font-weight: 600;
}

.agent-messages {
  flex: 1; overflow-y: auto; padding: 12px;
  display: flex; flex-direction: column; gap: 8px;
}

.agent-input {
  padding: 8px 12px;
  border-top: 1px solid var(--el-border-color-light);
}

.msg-bubble {
  padding: 8px 12px; border-radius: 8px;
  font-size: 13px; line-height: 1.5; max-width: 85%;
}
.user-msg { background: var(--el-color-primary-light-8); align-self: flex-end; }
.assistant-msg { align-self: flex-start; }

.msg-code {
  background: var(--el-fill-color); border-radius: 8px; overflow: hidden;
}
.msg-code .code-header {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 10px; font-size: 11px; color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-light);
}
.msg-code pre { margin: 0; padding: 10px; overflow-x: auto; font-size: 11px; }
.msg-error { color: var(--el-color-danger); font-size: 12px; }
.msg-status { color: var(--el-text-color-secondary); font-size: 12px; display: flex; align-items: center; gap: 6px; }

.agent-panel-enter-active,
.agent-panel-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.agent-panel-enter-from,
.agent-panel-leave-to { opacity: 0; transform: translateY(12px) scale(0.96); pointer-events: none; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add -A && git commit -m "feat: AgentChat chat component"
```

---

### Task 7: AppLayout 集成替换

**Files:**
- Modify: `web/src/components/AppLayout.vue` — 替换 OpenCode iframe 为 AgentChat

- [ ] **Step 1: 替换模板**

Remove the opencode iframe block (`<el-tooltip>...<Teleport>...</Teleport>`) and replace with:

```vue
<AgentChat />
```

In the imports:

```vue
import AgentChat from '@/components/AgentChat.vue'
```

Remove the old `.opencode-float`, `.opencode-panel`, `.opencode-panel-header`, `.opencode-iframe`, `.opencode-panel-enter-*` styles.

- [ ] **Step 2: 验证**

```bash
cd /Users/zhongding/dev/thingsboard/web && npx vue-tsc --noEmit
```

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: replace OpenCode iframe with AgentChat component"
```

---

### Task 8: Docker + 端到端验证

**Files:**
- Modify: `Dockerfile` — 安装 openai 依赖
- Modify: `docker-compose.yml` — 环境变量

- [ ] **Step 1: 更新 Docker 依赖**

```bash
cd /Users/zhongding/dev/thingsboard && docker compose build backend-api 2>&1 | tail -3
```

- [ ] **Step 2: 添加环境变量**

在 `docker-compose.yml` 的 `backend-api` 服务中：

```yaml
    environment:
      ...
      OPENAI_API_KEY: "${OPENAI_API_KEY:-}"
```

- [ ] **Step 3: 重启**

```bash
docker compose up -d backend-api
```

- [ ] **Step 4: 验证端点**

```bash
curl -s -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "1+1等于几"}' | head -5
```

Expected: SSE 流式响应
