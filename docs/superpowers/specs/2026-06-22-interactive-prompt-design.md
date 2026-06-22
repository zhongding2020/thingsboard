# Chat 交互式 Prompt 统一机制设计

> 将"agent 需要用户输入"的场景从纯文本输入升级为结构化交互组件（下拉、级联、多选、确认），建立从后端到前端的统一机制。

## 动机

当前 agent chat 所有交互都是纯文本：agent 通过 Markdown 表格返回产线/设备/参数列表，用户阅读后在 textarea 手动输入名称。这导致：
- 输入体验差（需打字精确匹配名称）
- 容易出错（拼写错误、名称不匹配）
- 工作流引导能力弱（无法约束输入范围）

需要一个统一机制，让 agent 能向前端发出结构化交互请求，前端渲染为下拉选择、级联选择、多选勾选、确认按钮等原生组件。

## 设计方案：消息 Action 扩展（方案 C）

### 核心思路

不在 SSE 协议层新增事件类型，而是扩展 `ChatMessage` 数据结构：agent 消息可附带 `actions` 数组。前端渲染消息时检查 `actions`，在消息卡片内嵌入交互组件。交互痕迹完整保留在消息历史中。

### Action Schema

```typescript
type InteractionType = 'select' | 'multi_select' | 'confirm' | 'input' | 'cascader'

interface Action {
  id: string                     // 唯一标识，如 "act_001"
  type: InteractionType
  title: string                  // 提示文本
  description?: string           // 补充说明
  required?: boolean             // 默认 true
  options?: ActionOption[]       // select / multi_select
  cascaderLevels?: CascaderLevel[] // cascader
  confirmText?: string           // confirm 确认按钮文案
  cancelText?: string            // confirm 取消按钮文案
  placeholder?: string           // input 类型
  defaultValue?: unknown
}

interface ActionOption {
  label: string
  value: string
  description?: string
  disabled?: boolean
}

interface CascaderLevel {
  key: string                    // 如 "line_id", "device_id"
  label: string                  // 如 "产线", "设备"
  options: ActionOption[]        // V1 必须预填充；动态加载（null）预留后续版本
}
```

### 后端集成：`ask_user` 工具

创建一个特殊的 `ask_user` 工具。Agent 调用它时，SSE 层拦截并发出 `interactive.prompt` 事件，**不执行工具体**。用户在前端操作后，响应作为该 tool call 的结果注入回 agent。

```
Agent 调用 ask_user({type:"select", title:"请选择产线", options:[...]})
    ↓
SSE 层拦截 → 不执行工具体 → 发出 interactive.prompt SSE 事件
    ↓
前端渲染 <ActionSelect /> → 用户选择 "注塑A线"
    ↓
POST /chat {action_responses: [{action_id:"act_001", value:{line_id:"L1"}}]}
    ↓
SSE 层构造 ToolMessage(content=action_response, tool_call_id=记录的id)
    ↓
ToolMessage 注入 agent 消息历史 → agent 继续执行，读到 tool result
```

### SSE 事件定义

```json
{
  "type": "interactive.prompt",
  "action": {
    "id": "act_001",
    "type": "select",
    "title": "请选择产线",
    "options": [
      {"label": "注塑A线", "value": "L1", "description": "3台设备"},
      {"label": "注塑B线", "value": "L2", "description": "2台设备"}
    ]
  }
}
```

### 前端渲染架构

```
MessageCard (assistant)
├── TextBlock                    ← Markdown 正文（已有）
├── InteractiveActions          ← NEW，嵌入消息气泡内
│   ├── ActionSelect            ← type="select"
│   ├── ActionMultiSelect       ← type="multi_select"
│   ├── ActionConfirm           ← type="confirm"
│   ├── ActionInput             ← type="input"
│   └── ActionCascader          ← type="cascader"，支持动态加载下级
├── ToolCallCard[]               ← 已有
└── SubagentCard[]               ← 已有
```

**行为规则：**
1. **单次性** — 操作后 action 变为 `resolved`，渲染为只读摘要（`✅ 产线：注塑A线`），不可重复点击
2. **可串联** — 一条消息可有多个 actions，按数组顺序渲染
3. **流式兼容** — actions 在正文输出完成后到达，不阻塞流式显示
4. **输入区保留** — 底部 textarea 始终存在，交互在消息卡片内完成
5. **自动提交** — 用户完成交互后前端自动构造 POST，无需手动输入

**状态生命周期：**
```
pending → submitting → resolved / rejected
```

### 消息历史中的交互痕迹

用户响应后，消息历史记录完整交互过程，刷新页面可恢复：

```json
[
  {"role": "assistant", "content": "请选择要分析的产线：", "actions": [{"id":"act_001","type":"select","title":"请选择产线",...}]},
  {"role": "user", "content": "选择 注塑A线", "action_responses": [{"action_id":"act_001","value":{"line_id":"L1","line_name":"注塑A线"}}]}
]
```

## 交互场景覆盖

### 场景 1：工作流 Define — 级联选择产线/设备

Agent 调用 `ask_user({type:"cascader", levels:[{key:"line_id",label:"产线"}, {key:"device_id",label:"设备"}]})`。前端渲染级联选择器，用户逐级点选。

### 场景 2：分析参数选择 — 多选勾选

Agent 调用 `ask_user({type:"multi_select", options:[{label:"注塑温度","value":"temp"},...]})`。前端渲染 checkbox 组。

### 场景 3：参数集审批 — 确认/驳回按钮

Agent 调用 `ask_user({type:"confirm", title:"确认批准此参数集？", confirmText:"批准", cancelText:"驳回"})`。前端渲染两个按钮，只有在用户明确点击后才执行。

### 场景 4：补充信息 — 结构化输入

Agent 调用 `ask_user({type:"input", title:"请输入目标 Cpk 值", placeholder:"例如 1.33"})`。前端渲染单行输入框。

## 改动文件

| 层 | 文件 | 改动 |
|---|---|---|
| 后端工具 | `src/process_opt/agent/tools/system_tools.py` | 新增 `ask_user` 工具（仅签名，无实现体） |
| SSE 层 | `src/process_opt/api/agent_routes.py` | `_map_event()` 识别 `ask_user` → 发出 `interactive.prompt`；`/chat` 路由处理 `action_response` → 构造 `ToolMessage` |
| 前端 composable | `web/src/composables/useAgentStream.ts` | 新增 `interactive.prompt` case，管理 pending actions |
| 前端组件 | `web/src/components/agent/InteractiveActions.vue` | 新增容器组件，根据 type 分发子组件 |
| 前端组件 | `web/src/components/agent/ActionSelect.vue` | 下拉选择（基于 Element Plus `el-select`） |
| 前端组件 | `web/src/components/agent/ActionMultiSelect.vue` | 多选勾选（基于 Element Plus `el-checkbox-group`） |
| 前端组件 | `web/src/components/agent/ActionConfirm.vue` | 确认/取消按钮组 |
| 前端组件 | `web/src/components/agent/ActionInput.vue` | 结构化输入框 |
| 前端组件 | `web/src/components/agent/ActionCascader.vue` | 级联选择，支持动态加载 |
| 前端消息 | `web/src/components/agent/MessageCard.vue` | 在 TextBlock 后、ToolCallCard 前插入 InteractiveActions |
| 前端类型 | `web/src/composables/useAgentStream.ts` | ChatMessage 扩展 `actions` 字段 |

## 约束

- 不改变现有 SSE 事件类型名称（`message.delta`、`tool.call` 等保持不变）
- 不改变现有 `POST /chat` 路由签名（仅扩展 body 支持可选 `action_responses`）
- Element Plus 已在项目中可用，复用其 `el-select`、`el-checkbox-group` 等组件
- 交互组件渲染在消息气泡内，不替换底部 textarea
- 消息历史中的 actions 必须可序列化（JSON），刷新页面后可恢复
