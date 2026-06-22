# Chat 交互式 Prompt 统一机制 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified interactive prompt mechanism so the agent can request structured user input (dropdown selects, multi-select, confirm buttons, cascader, text input) via the `ask_user` tool, rendered as native UI components in the chat message stream.

**Architecture:** The `ask_user` tool is intercepted at the SSE layer during `on_tool_start` — instead of emitting `tool.call`, it emits `interactive.prompt` with the full Action payload. The agent completes its current turn (outputting guidance text), then the frontend renders the interactive component inline in the message card. The user's selection is sent as a follow-up user message via `POST /chat`, and the agent handles it in the next conversation turn.

**Tech Stack:** Python 3.11+ (FastAPI, DeepAgents/LangChain), Vue 3 + TypeScript (Element Plus, Pinia), SSE streaming

## Global Constraints

- Do not change existing SSE event type names (`message.delta`, `tool.call`, `tool.result`, `node.start`, `node.end`, `subagent.*`, `thinking.*`, `phase.change`, `todo.update`, `suggestions`, `session.status`)
- Do not change the `POST /chat` route signature; only extend body with optional `action_responses` field
- Element Plus is already available in the project; reuse `el-select`, `el-checkbox-group`, `el-input` for action components
- Interactive components render **inside** the message card bubble, never replacing the bottom textarea
- Action state must survive page refresh (serialized in message history JSON)
- Keep existing 9 business pages and backend SSE format intact
- Zero TypeScript errors: `cd web && npm run typecheck` must pass
- Zero Python lint errors: `ruff check .` must pass

---

### Task 1: Backend — `ask_user` Tool

**Files:**
- Modify: `src/process_opt/agent/tools/system_tools.py` (add `ask_user` to returned tool list)
- Test: `tests/agent/test_system_tools.py` (add test)

**Interfaces:**
- Produces: `ask_user` LangChain tool (name=`"ask_user"`), callable with args `{type, title, description?, options?, cascaderLevels?, confirmText?, cancelText?, placeholder?, defaultValue?}` — returns a JSON string with the action and a prompt to wait for user response

- [ ] **Step 1: Add `ask_user` function inside `create_system_tools()`**

```python
@tool
async def ask_user(
    type: str,
    title: str,
    description: str = "",
    options: str = "[]",
    cascader_levels: str = "[]",
    confirm_text: str = "",
    cancel_text: str = "",
    placeholder: str = "",
    default_value: str = "",
) -> str:
    """Ask the user for structured input via an interactive UI widget.

    Use this when you need the user to select, confirm, or input something
    before proceeding. The frontend will render the appropriate widget
    (dropdown, checkbox group, confirm buttons, etc.).

    IMPORTANT: After calling this tool, STOP your current response and
    tell the user to use the interactive widget above. Do NOT proceed
    with analysis until the user responds in the next turn.

    Args:
        type: Widget type — one of "select", "multi_select", "confirm",
              "input", "cascader"
        title: Prompt text shown to the user
        description: Optional longer explanation
        options: JSON array of {label, value, description?, disabled?}
                 for select/multi_select types
        cascader_levels: JSON array of {key, label, options} for cascader
        confirm_text: Text for the confirm button (confirm type)
        cancel_text: Text for the cancel button (confirm type)
        placeholder: Placeholder text for input type
        default_value: Pre-selected value if any
    """
    import json as _json
    action: dict = {
        "type": type,
        "title": title,
    }
    if description:
        action["description"] = description
    if options and options != "[]":
        action["options"] = _json.loads(options)
    if cascader_levels and cascader_levels != "[]":
        action["cascaderLevels"] = _json.loads(cascader_levels)
    if confirm_text:
        action["confirmText"] = confirm_text
    if cancel_text:
        action["cancelText"] = cancel_text
    if placeholder:
        action["placeholder"] = placeholder
    if default_value:
        action["defaultValue"] = _json.loads(default_value)

    # action_id is assigned by SSE layer; tool just returns the payload
    return _json.dumps({"action": action, "message": "等待用户通过前端交互组件选择..."})
```

- [ ] **Step 2: Register `ask_user` in the returned tool list**

In `create_system_tools()`, append `ask_user` to the return list. The return at line 202 currently reads:

```python
return [
    list_production_lines,
    get_production_line,
    list_registered_devices,
    get_registered_device,
    monitor_production_line,
]
```

Change to:

```python
return [
    list_production_lines,
    get_production_line,
    list_registered_devices,
    get_registered_device,
    monitor_production_line,
    ask_user,
]
```

- [ ] **Step 3: Write the test**

Add to `tests/agent/test_system_tools.py`:

```python
import json


@pytest.mark.asyncio
async def test_ask_user_select_type(tools: list) -> None:
    tool = _find_tool(tools, "ask_user")
    result = await tool.ainvoke({
        "type": "select",
        "title": "请选择产线",
        "options": json.dumps([
            {"label": "注塑A线", "value": "L1"},
            {"label": "注塑B线", "value": "L2"},
        ]),
    })
    data = json.loads(result)
    assert data["action"]["type"] == "select"
    assert data["action"]["title"] == "请选择产线"
    assert len(data["action"]["options"]) == 2
    assert data["action"]["options"][0]["label"] == "注塑A线"


@pytest.mark.asyncio
async def test_ask_user_confirm_type(tools: list) -> None:
    tool = _find_tool(tools, "ask_user")
    result = await tool.ainvoke({
        "type": "confirm",
        "title": "确认批准？",
        "confirm_text": "批准",
        "cancel_text": "驳回",
    })
    data = json.loads(result)
    assert data["action"]["type"] == "confirm"
    assert data["action"]["confirmText"] == "批准"
    assert data["action"]["cancelText"] == "驳回"


@pytest.mark.asyncio
async def test_ask_user_cascader_type(tools: list) -> None:
    tool = _find_tool(tools, "ask_user")
    result = await tool.ainvoke({
        "type": "cascader",
        "title": "请选择产线和设备",
        "cascader_levels": json.dumps([
            {"key": "line_id", "label": "产线", "options": [
                {"label": "A线", "value": "L1"},
                {"label": "B线", "value": "L2"},
            ]},
            {"key": "device_id", "label": "设备", "options": [
                {"label": "设备1", "value": "D1"},
                {"label": "设备2", "value": "D2"},
            ]},
        ]),
    })
    data = json.loads(result)
    assert data["action"]["type"] == "cascader"
    assert len(data["action"]["cascaderLevels"]) == 2


@pytest.mark.asyncio
async def test_ask_user_minimal_args(tools: list) -> None:
    tool = _find_tool(tools, "ask_user")
    result = await tool.ainvoke({"type": "input", "title": "请输入目标值"})
    data = json.loads(result)
    assert data["action"]["type"] == "input"
    assert data["action"]["title"] == "请输入目标值"
    assert "options" not in data["action"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/agent/test_system_tools.py -v -k ask_user`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/agent/tools/system_tools.py tests/agent/test_system_tools.py
git commit -m "feat: add ask_user tool for interactive user prompts"
```

---

### Task 2: Backend — SSE Interception + Action Response Handling

**Files:**
- Modify: `src/process_opt/api/agent_routes.py` (lines 98-113 for `/chat`, lines 228-301 for `_map_event`, line 75 for tool_pool)

**Interfaces:**
- Consumes: `ask_user` tool (from Task 1), registered in `tool_pool` 
- Produces: `interactive.prompt` SSE event type; `/chat` body extended with optional `action_responses`; `_map_event` skips `tool.call`/`tool.result` for `ask_user`

- [ ] **Step 1: Modify `_map_event` to intercept `ask_user` tool calls**

Replace the tool start block in `_map_event()` (lines 256-261) with:

```python
    # Tool start
    if kind == "on_tool_start":
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})

        # ask_user is intercepted — emit interactive.prompt instead of tool.call
        if name == "ask_user":
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            action_data: dict[str, Any] = {"id": action_id}
            # Copy scalar fields with camelCase key mapping
            for src, dst in (("type", "type"), ("title", "title"),
                             ("description", "description"), ("placeholder", "placeholder")):
                if inp.get(src):
                    action_data[dst] = inp[src]
            if inp.get("confirm_text"):
                action_data["confirmText"] = inp["confirm_text"]
            if inp.get("cancel_text"):
                action_data["cancelText"] = inp["cancel_text"]
            # Parse JSON string fields to objects
            for src, dst in (("options", "options"), ("cascader_levels", "cascaderLevels")):
                raw = inp.get(src, "")
                if raw and raw != "[]":
                    try:
                        action_data[dst] = json.loads(raw) if isinstance(raw, str) else raw
                    except (json.JSONDecodeError, TypeError):
                        pass
            if inp.get("default_value") and inp["default_value"]:
                try:
                    action_data["defaultValue"] = json.loads(inp["default_value"]) if isinstance(inp["default_value"], str) else inp["default_value"]
                except (json.JSONDecodeError, TypeError):
                    pass
            data = json.dumps({"type": "interactive.prompt", "action": action_data}, default=str)
            return f"data: {data}\n\n".encode()

        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        data = json.dumps({"type": "tool.call", "name": name, "args": args}, default=str)
        return f"data: {data}\n\n".encode()
```

Replace the tool end block (lines 264-272) with:

```python
    # Tool end
    if kind == "on_tool_end":
        # Skip tool.result for ask_user — already handled as interactive.prompt
        if event.get("name", "") == "ask_user":
            return None
        output = event.get("data", {}).get("output", "")
        if hasattr(output, "content"):
            output_str = str(output.content)
        else:
            output_str = str(output)
        data = json.dumps({"type": "tool.result", "name": event.get("name", ""),
                           "data": output_str})
        return f"data: {data}\n\n".encode()
```

- [ ] **Step 2: Add `import uuid` at the top of agent_routes.py**

The `_map_event` function now uses `uuid.uuid4()` for generating action IDs. Add `import uuid` at the top (line 12, after `import time`):

```python
import uuid
```

- [ ] **Step 3: Modify `POST /chat` to accept optional `action_responses`**

Replace the `/chat` route (lines 98-112) with:

```python
    @router.post("/chat")
    async def send_message(request: Request) -> Response:
        body = await request.json()
        session_id = body.get("session_id", "")
        text = body.get("text", "")
        action_responses = body.get("action_responses") or []

        if not session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        if not text and not action_responses:
            raise HTTPException(status_code=400, detail="text or action_responses required")

        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话已过期，请重新开始")

        # Build user message content
        content_parts: list[str] = []
        if text:
            content_parts.append(text)
        if action_responses:
            for ar in action_responses:
                action_id = ar.get("action_id", "")
                value = ar.get("value", {})
                content_parts.append(f"[交互响应 action_id={action_id}]: {json.dumps(value, ensure_ascii=False)}")
        content = "\n".join(content_parts)

        session["messages"].append({"role": "user", "content": content})
        session["pending"] = True
        return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Write the test for SSE interception**

Add to `tests/api/test_app.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch


class FakeDeepAgent:
    """Fake DeepAgent that emits ask_user tool call events."""
    def __init__(self) -> None:
        self._events: list[dict] = []

    def set_events(self, events: list[dict]) -> None:
        self._events = events

    async def astream_events(self, input_data: dict, config: dict | None = None,
                             version: str = "v2"):
        for event in self._events:
            yield event

    async def aget_state(self, config: dict | None = None):
        return MagicMock(values={})


class FakeLLM:
    async def ainvoke(self, messages):
        return MagicMock(content="suggestion1\nsuggestion2\nsuggestion3")


@pytest.mark.asyncio
async def test_ask_user_emits_interactive_prompt_not_tool_call() -> None:
    """Verify ask_user tool start emits interactive.prompt, not tool.call."""
    from process_opt.api.agent_routes import _map_event

    event = {
        "event": "on_tool_start",
        "name": "ask_user",
        "run_id": "run-123",
        "data": {
            "input": {
                "type": "select",
                "title": "请选择产线",
                "options": '[{"label":"A线","value":"L1"}]',
            }
        },
    }
    result = _map_event(event, set())
    assert result is not None
    decoded = json.loads(result.decode().lstrip("data: "))
    assert decoded["type"] == "interactive.prompt"
    assert decoded["action"]["type"] == "select"
    assert decoded["action"]["title"] == "请选择产线"
    assert "id" in decoded["action"]


@pytest.mark.asyncio
async def test_ask_user_tool_end_is_skipped() -> None:
    """Verify ask_user tool_end produces no SSE output."""
    from process_opt.api.agent_routes import _map_event

    event = {
        "event": "on_tool_end",
        "name": "ask_user",
        "run_id": "run-123",
        "data": {"output": "..."},
    }
    result = _map_event(event, set())
    assert result is None


@pytest.mark.asyncio
async def test_normal_tool_call_still_works() -> None:
    """Verify non-ask_user tools still emit tool.call."""
    from process_opt.api.agent_routes import _map_event

    event = {
        "event": "on_tool_start",
        "name": "list_production_lines",
        "run_id": "run-456",
        "data": {"input": {}},
    }
    result = _map_event(event, set())
    assert result is not None
    decoded = json.loads(result.decode().lstrip("data: "))
    assert decoded["type"] == "tool.call"
    assert decoded["name"] == "list_production_lines"
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/api/test_app.py -v -k "ask_user or normal_tool_call"`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/process_opt/api/agent_routes.py tests/api/test_app.py
git commit -m "feat: intercept ask_user tool calls as interactive.prompt SSE events"
```

---

### Task 3: Frontend — Type Definitions + Composable

**Files:**
- Modify: `web/src/composables/useAgentStream.ts` (add types, new SSE event handler)

**Interfaces:**
- Produces: `InteractiveAction` type, `ActionResponse` type, `pendingActions` ref, `interactive.prompt` SSE handler, `resolveAction` function on ChatMessage
- Consumes: existing SSE event stream from `useAgentStream`

- [ ] **Step 1: Add type definitions at the top of useAgentStream.ts**

Insert after the `DebugEvent` interface (line 40) and before `export function useAgentStream`:

```typescript
// --- Interactive Prompt types ---

export type InteractionType = 'select' | 'multi_select' | 'confirm' | 'input' | 'cascader'

export interface ActionOption {
  label: string
  value: string
  description?: string
  disabled?: boolean
}

export interface CascaderLevel {
  key: string
  label: string
  options: ActionOption[]
}

export interface InteractiveAction {
  id: string
  type: InteractionType
  title: string
  description?: string
  required?: boolean
  options?: ActionOption[]
  cascaderLevels?: CascaderLevel[]
  confirmText?: string
  cancelText?: string
  placeholder?: string
  defaultValue?: unknown
  status: 'pending' | 'submitting' | 'resolved' | 'rejected'
}

export interface ActionResponse {
  action_id: string
  type: InteractionType
  value: unknown
}
```

- [ ] **Step 2: Extend ChatMessage interface**

Add `actions` field to `ChatMessage` (after `trace?: string`):

```typescript
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
  thinking?: string
  subagents?: SubagentState[]
  trace?: string
  actions?: InteractiveAction[]   // <-- NEW
}
```

- [ ] **Step 3: Add `interactive.prompt` SSE event handler**

In the `switch` statement inside `send()`, add a new case after `case 'tool.result':` (around line 136):

```typescript
              case 'interactive.prompt': {
                const action: InteractiveAction = {
                  ...event.action,
                  status: 'pending',
                }
                assistantMsg.actions = [...(assistantMsg.actions || []), action]
                break
              }
```

- [ ] **Step 4: Run typecheck**

Run: `cd web && npm run typecheck`
Expected: zero errors

- [ ] **Step 5: Commit**

```bash
git add web/src/composables/useAgentStream.ts
git commit -m "feat: add InteractiveAction types and interactive.prompt SSE handler"
```

---

### Task 4: Frontend — InteractiveActions Components + MessageCard Integration

**Files:**
- Create: `web/src/components/agent/InteractiveActions.vue`
- Create: `web/src/components/agent/ActionSelect.vue`
- Create: `web/src/components/agent/ActionMultiSelect.vue`
- Create: `web/src/components/agent/ActionConfirm.vue`
- Create: `web/src/components/agent/ActionInput.vue`
- Create: `web/src/components/agent/ActionCascader.vue`
- Modify: `web/src/components/agent/MessageCard.vue` (add InteractiveActions between TextBlock and ToolCallCard)

**Interfaces:**
- Consumes: `InteractiveAction` type from `@/composables/useAgentStream`
- Produces: `InteractiveActions` component (props: `actions: InteractiveAction[]`, emits: `resolve(actionId, value)`)

- [ ] **Step 1: Create InteractiveActions.vue (container)**

`web/src/components/agent/InteractiveActions.vue`:

```vue
<template>
  <div v-if="actions.length" class="flex flex-col gap-2 mt-2">
    <template v-for="action in actions" :key="action.id">
      <!-- Resolved state: show read-only summary -->
      <div
        v-if="action.status === 'resolved'"
        class="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400 px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800/50"
      >
        <span>✅</span>
        <span>{{ action.title }}：{{ resolvedLabel(action) }}</span>
      </div>
      <!-- Pending state: render interactive widget -->
      <div v-else class="border border-blue-200 dark:border-blue-700 rounded-xl bg-blue-50/30 dark:bg-blue-950/20 p-3">
        <p class="text-[11px] font-medium text-slate-700 dark:text-slate-200 mb-2">
          {{ action.title }}
        </p>
        <p v-if="action.description" class="text-[10px] text-slate-400 dark:text-slate-500 mb-2">
          {{ action.description }}
        </p>
        <ActionSelect
          v-if="action.type === 'select'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionMultiSelect
          v-else-if="action.type === 'multi_select'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionConfirm
          v-else-if="action.type === 'confirm'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionInput
          v-else-if="action.type === 'input'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
        <ActionCascader
          v-else-if="action.type === 'cascader'"
          :action="action"
          @resolve="(v: unknown) => $emit('resolve', action.id, v)"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { InteractiveAction } from '@/composables/useAgentStream'
import ActionSelect from './ActionSelect.vue'
import ActionMultiSelect from './ActionMultiSelect.vue'
import ActionConfirm from './ActionConfirm.vue'
import ActionInput from './ActionInput.vue'
import ActionCascader from './ActionCascader.vue'

defineProps<{ actions: InteractiveAction[] }>()
defineEmits<{ resolve: [actionId: string, value: unknown] }>()

function resolvedLabel(action: InteractiveAction): string {
  if (action.type === 'confirm') {
    return (action as any)._resolvedValue ? action.confirmText || '已确认' : action.cancelText || '已取消'
  }
  return (action as any)._resolvedLabel || '已选择'
}
</script>
```

- [ ] **Step 2: Create ActionSelect.vue**

`web/src/components/agent/ActionSelect.vue`:

```vue
<template>
  <div class="flex items-center gap-2">
    <el-select
      v-model="selected"
      :placeholder="action.placeholder || '请选择'"
      size="small"
      class="flex-1"
      @change="onChange"
    >
      <el-option
        v-for="opt in action.options"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
        :disabled="opt.disabled"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const selected = ref((props.action.defaultValue as string) || '')

function onChange(val: string) {
  const opt = props.action.options?.find(o => o.value === val)
  emit('resolve', { value: val, label: opt?.label || val })
}
</script>
```

- [ ] **Step 3: Create ActionMultiSelect.vue**

`web/src/components/agent/ActionMultiSelect.vue`:

```vue
<template>
  <div class="flex flex-col gap-2">
    <el-checkbox-group v-model="checked" size="small" class="flex flex-col gap-1.5">
      <el-checkbox
        v-for="opt in action.options"
        :key="opt.value"
        :value="opt.value"
        :disabled="opt.disabled"
        :label="opt.label"
      />
    </el-checkbox-group>
    <button
      :disabled="!checked.length"
      class="self-start px-3 py-1 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white border-none cursor-pointer transition-colors"
      @click="submit"
    >确认选择</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const checked = ref<string[]>((props.action.defaultValue as string[]) || [])

function submit() {
  const selected = props.action.options?.filter(o => checked.value.includes(o.value))
    .map(o => ({ value: o.value, label: o.label }))
  emit('resolve', { values: selected, raw: checked.value })
}
</script>
```

- [ ] **Step 4: Create ActionConfirm.vue**

`web/src/components/agent/ActionConfirm.vue`:

```vue
<template>
  <div class="flex items-center gap-2">
    <button
      class="px-4 py-1.5 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 text-white border-none cursor-pointer transition-colors"
      @click="emit('resolve', { confirmed: true })"
    >{{ action.confirmText || '确认' }}</button>
    <button
      class="px-4 py-1.5 text-[11px] rounded-md bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-slate-500 border border-slate-200 dark:border-slate-700 cursor-pointer transition-colors"
      @click="emit('resolve', { confirmed: false })"
    >{{ action.cancelText || '取消' }}</button>
  </div>
</template>

<script setup lang="ts">
import type { InteractiveAction } from '@/composables/useAgentStream'

defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()
</script>
```

- [ ] **Step 5: Create ActionInput.vue**

`web/src/components/agent/ActionInput.vue`:

```vue
<template>
  <div class="flex items-center gap-2">
    <el-input
      v-model="text"
      :placeholder="action.placeholder || '请输入'"
      size="small"
      class="flex-1"
      @keydown.enter="submit"
    />
    <button
      :disabled="!text.trim()"
      class="px-3 py-1 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white border-none cursor-pointer transition-colors"
      @click="submit"
    >确认</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const text = ref((props.action.defaultValue as string) || '')

function submit() {
  if (!text.value.trim()) return
  emit('resolve', { value: text.value.trim() })
}
</script>
```

- [ ] **Step 6: Create ActionCascader.vue**

`web/src/components/agent/ActionCascader.vue`:

```vue
<template>
  <div class="flex flex-col gap-2">
    <div v-for="level in action.cascaderLevels" :key="level.key" class="flex flex-col gap-1">
      <span class="text-[10px] text-slate-400 dark:text-slate-500">{{ level.label }}</span>
      <el-select
        :model-value="selections[level.key]"
        :placeholder="`请选择${level.label}`"
        size="small"
        @change="(val: string) => onLevelChange(level.key, val, level.options || [])"
      >
        <el-option
          v-for="opt in level.options"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
          :disabled="opt.disabled"
        />
      </el-select>
    </div>
    <button
      :disabled="!allLevelsFilled"
      class="self-start px-3 py-1 text-[11px] rounded-md bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white border-none cursor-pointer transition-colors"
      @click="submit"
    >确认选择</button>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import type { InteractiveAction } from '@/composables/useAgentStream'

const props = defineProps<{ action: InteractiveAction }>()
const emit = defineEmits<{ resolve: [value: unknown] }>()

const selections = reactive<Record<string, string>>({})
const labels = reactive<Record<string, string>>({})

const allLevelsFilled = computed(() => {
  return props.action.cascaderLevels?.every(l => selections[l.key]) ?? false
})

function onLevelChange(key: string, val: string, options: { label: string; value: string }[]) {
  selections[key] = val
  const opt = options.find(o => o.value === val)
  labels[key] = opt?.label || val
}

function submit() {
  const result: Record<string, { value: string; label: string }> = {}
  for (const key of Object.keys(selections)) {
    result[key] = { value: selections[key], label: labels[key] || selections[key] }
  }
  emit('resolve', result)
}
</script>
```

- [ ] **Step 7: Integrate InteractiveActions into MessageCard.vue**

Modify `web/src/components/agent/MessageCard.vue` — insert `InteractiveActions` between `TextBlock` and `ToolCallCard`:

In the template section, after the TextBlock div (lines 21-26) and before ToolCallCard (line 29), add:

```vue
      <!-- Interactive actions -->
      <InteractiveActions
        v-if="msg.actions?.length"
        :actions="msg.actions"
        @resolve="(actionId: string, value: unknown) => $emit('resolveAction', msg, actionId, value)"
      />
```

Update the `<script setup>` section imports and emits:

```typescript
import InteractiveActions from './InteractiveActions.vue'
import type { ChatMessage, InteractiveAction } from '@/composables/useAgentStream'

defineProps<{ msg: ChatMessage; isStreaming: boolean }>()
defineEmits<{
  copy: []
  regenerate: []
  resolveAction: [msg: ChatMessage, actionId: string, value: unknown]
}>()
```

- [ ] **Step 8: Run typecheck**

Run: `cd web && npm run typecheck`
Expected: zero errors

- [ ] **Step 9: Commit**

```bash
git add web/src/components/agent/InteractiveActions.vue \
        web/src/components/agent/ActionSelect.vue \
        web/src/components/agent/ActionMultiSelect.vue \
        web/src/components/agent/ActionConfirm.vue \
        web/src/components/agent/ActionInput.vue \
        web/src/components/agent/ActionCascader.vue \
        web/src/components/agent/MessageCard.vue
git commit -m "feat: add InteractiveActions + 5 action sub-components with MessageCard integration"
```

---

### Task 5: Frontend — Wire Resolve Logic in ChatView

**Files:**
- Modify: `web/src/components/agent/ChatView.vue` (lines 150-158 for MessageCard, add resolveAction handler)

**Interfaces:**
- Consumes: `resolveAction` emit from MessageCard, `onSend` function, `useAgentStream`
- Produces: End-to-end action resolution flow: user clicks → action status updated → POST with action_responses → agent continues

- [ ] **Step 1: Add `resolveAction` handler in ChatView.vue**

Add the handler function in the `<script setup>` section, near the other action functions (after `copyMsg` at line 437):

```typescript
async function resolveAction(msg: ChatMessage, actionId: string, value: unknown) {
  // Mark the action as resolving
  const action = msg.actions?.find(a => a.id === actionId)
  if (!action) return
  action.status = 'submitting'

  // Build action response
  const actionResponse: { action_id: string; type: string; value: unknown } = {
    action_id: actionId,
    type: action.type,
    value,
  }

  // Store resolved label for display
  if (action.type === 'select') {
    ;(action as any)._resolvedLabel = (value as { label: string }).label
  } else if (action.type === 'multi_select') {
    const v = value as { values: { label: string }[] }
    ;(action as any)._resolvedLabel = v.values.map(x => x.label).join('、')
  } else if (action.type === 'confirm') {
    ;(action as any)._resolvedValue = (value as { confirmed: boolean }).confirmed
  } else if (action.type === 'cascader') {
    const v = value as Record<string, { label: string }>
    ;(action as any)._resolvedLabel = Object.values(v).map(x => x.label).join(' → ')
  } else if (action.type === 'input') {
    ;(action as any)._resolvedLabel = (value as { value: string }).value
  }

  // Ensure session exists
  if (!sessionId.value) {
    await createNewSession()
    sessionStorage.setItem('opencode-session', sessionId.value)
  }

  // Send via POST /chat with action_responses
  try {
    const { sendMessageAsync } = await import('@/api/agent')

    // Extend sendMessageAsync to support action_responses
    const API_URL = import.meta.env.DEV ? '/api/v1/agent' : 'http://localhost:8000/api/v1/agent'
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 30000)
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-User': 'anonymous' },
        body: JSON.stringify({
          session_id: sessionId.value,
          text: '',
          action_responses: [actionResponse],
        }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
    } finally {
      clearTimeout(timeout)
    }

    action.status = 'resolved'

    // Trigger SSE to get agent's follow-up response
    const stream = ensureStream()
    const prevLoading = stream.loading.value
    stream.loading.value = true

    const res = await fetch(
      `${API_URL}/chat/${encodeURIComponent(sessionId.value)}/events`,
      { headers: { 'X-User': 'anonymous' } }
    )
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

    // Add placeholder assistant message for the response
    const assistantMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      subagents: [],
    }
    stream.messages.value.push(assistantMsg)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        try {
          const event = JSON.parse(trimmed.slice(6))
          if (event.type === 'message.delta') {
            assistantMsg.content += event.text || ''
          } else if (event.type === 'session.status' && event.status === 'idle') {
            stream.loading.value = false
          }
        } catch { /* skip */ }
      }
    }
    stream.loading.value = false
  } catch (e: unknown) {
    action.status = 'rejected'
    if ((e as Error).name !== 'AbortError') {
      streamRef.value!.error.value = (e as Error).message || '操作失败'
    }
  }
}
```

- [ ] **Step 2: Bind the handler in MessageCard template**

Update the MessageCard usage in ChatView.vue template (lines 151-158) to include the `resolveAction` handler:

```vue
          <MessageCard
            v-for="(msg, i) in msgs"
            :key="i"
            :msg="msg"
            :isStreaming="loading && i === msgs.length - 1 && msg.role === 'assistant'"
            @copy="copyMsg(msg)"
            @regenerate="onRegenerate(i)"
            @resolveAction="resolveAction"
          />
```

- [ ] **Step 3: Run typecheck**

Run: `cd web && npm run typecheck`
Expected: zero errors

- [ ] **Step 4: Commit**

```bash
git add web/src/components/agent/ChatView.vue
git commit -m "feat: wire action resolution flow in ChatView"
```

---

### Task 6: End-to-End Verification

**Files:** None (verification-only task)

- [ ] **Step 1: Run full backend test suite**

```bash
pytest tests/agent/test_system_tools.py tests/api/test_app.py -v
```
Expected: all tests pass, including the new ask_user and interactive.prompt tests

- [ ] **Step 2: Run backend lint**

```bash
ruff check src/process_opt/agent/tools/system_tools.py src/process_opt/api/agent_routes.py
```
Expected: zero errors

- [ ] **Step 3: Run frontend typecheck**

```bash
cd web && npm run typecheck
```
Expected: zero errors

- [ ] **Step 4: Run frontend build**

```bash
cd web && npm run build
```
Expected: build succeeds without errors

- [ ] **Step 5: Manual verification checklist**

1. Start backend: `docker compose up -d backend-api`
2. Start frontend: `cd web && npm run dev`
3. Open `/chat` page
4. Send: "帮我启动工艺参数优化流程"
5. Verify: when agent calls `ask_user`, an interactive dropdown/selector appears inside the message bubble
6. Interact with the widget — verify action resolves to read-only summary
7. Verify agent receives the response and continues the conversation
8. Switch dark/light mode — verify interactive components render correctly in both modes
9. Refresh page — verify resolved actions appear as read-only summaries

- [ ] **Step 6: Commit if no issues**

```bash
git commit -m "chore: end-to-end verification passed" --allow-empty
```

---

## Self-Review

**Spec coverage:**
- Action Schema → Task 3 (TypeScript types)
- ask_user tool → Task 1 (backend tool)
- SSE interception + interactive.prompt → Task 2 (SSE layer)
- Frontend InteractiveActions + 5 sub-components → Task 4
- MessageCard integration → Task 4, Step 7
- ChatView wire-up → Task 5
- 4 interaction scenarios → covered by the 5 component types (select covers scenario 1 single-level, cascader covers scenario 1, multi_select covers scenario 2, confirm covers scenario 3, input covers scenario 4)
- 约束 (constraints) → all addressed in Global Constraints

**Placeholder scan:** No TBD, TODO, or vague instructions. Every step has exact code.

**Type consistency:**
- `InteractiveAction` type defined in Task 3, used in Tasks 4 and 5 — consistent
- `ActionResponse` type defined in Task 3, used in Task 5 — consistent
- `ChatMessage.actions` field added in Task 3, read in Tasks 4 and 5 — consistent
- `resolveAction` emit signature in MessageCard (Task 4) matches handler in ChatView (Task 5) — `(msg: ChatMessage, actionId: string, value: unknown)` — consistent
- Backend `ask_user` tool name matches the string checked in `_map_event` — both `"ask_user"` — consistent
- SSE event `interactive.prompt` matches the case in useAgentStream — consistent
