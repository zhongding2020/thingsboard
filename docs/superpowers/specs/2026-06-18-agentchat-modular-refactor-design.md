# AgentChat.vue 模块化重构设计

**日期**: 2026-06-18  
**目标**: 将 593 行单体 AgentChat.vue 拆分为小组件 + composable，降低复杂度，不引入新依赖

## 动机

当前 AgentChat.vue 承载了所有聊天功能（浮动按钮、侧边栏、消息渲染、SSE 流、文件上传、会话管理等），导致：
- 单文件 593 行，难以维护
- 模板/脚本/样式混杂，定位问题困难
- 富文本渲染逻辑（ECharts/Mermaid）与 UI 状态管理耦合

## 架构概览

### 组件树

```
AgentChat.vue (编排层, ~80行)
├── FloatingButton.vue          — 拖拽浮动按钮 (~50行)
├── AgentSidebar.vue            — 侧边栏面板 Teleport + 过渡 (~60行)
│   ├── AgentHeader.vue         — 模型/工艺选择器 + 按钮组 (~40行)
│   ├── SessionList.vue         — 历史会话列表 (~50行)
│   └── ChatView.vue            — 主聊天区域 (~70行)
│       ├── ChatBubble.vue      — 单条消息气泡 (~60行)
│       │   ├── ChatContent.vue — 富文本渲染 Markdown/图表 (~80行)
│       │   └── ChatToolCall.vue— 工具调用/思考过程折叠 (~40行)
│       ├── ChatLoading.vue     — 3点加载动画 (~15行)
│       ├── ChatSuggestions.vue — 建议问题 chips (~20行)
│       └── ChatInput.vue       — 输入框 + 文件上传 (~50行)
```

### Composables

| Composable | 职责 | 行数 |
|---|---|---|
| `useChatSession` | 会话 CRUD、sessionStorage 持久化、刷新/切换/删除 | ~80 |
| `useChatStream` | SSE fetch + ReadableStream、增量更新回调、取消控制 | ~100 |
| `useChatMessages` | messages 响应式数组、copyMessage/regenerateMessage | ~50 |
| `useFileUpload` | 文件选择、FormData 上传、自动触发分析消息 | ~50 |
| `useDrag` | 浮动按钮 mousedown/mousemove/mouseup 拖拽 | ~30 |

## 组件接口

### ChatView.vue (编排者)

挂载所有 composable，通过 provide 向下传递关键状态：
- `provide('chatMessages', messages)`
- `provide('chatSessions', sessions)`
- `provide('chatStreaming', loading)`

### ChatBubble.vue

```
Props:
  role: 'user' | 'assistant'
  parts: MessagePart[]
  msgIndex: number
  isStreaming: boolean

Emits:
  'regenerate': index
```

行为：
- user: 右对齐气泡，显示文案
- assistant: 遍历 parts，按 type 分发
  - `text / step-start / step-finish` → ChatContent
  - `reasoning / thinking` → ChatToolCall (collapsible)
  - `tool_call` → ChatToolCall (工具名 + args)
  - `tool_result` → ChatToolCall (截断 500 字符)
- 非流式消息末尾显示 复制/重新生成 按钮

### ChatContent.vue

```
Props:
  text: string
```

纯渲染组件，无 emits。逻辑从现有 `renderContent()` 迁移：
- 调用 `marked.parse()` 渲染 Markdown
- onMounted/onUpdated 中扫描 ECharts/Mermaid 块并初始化
- 需要唯一 ID 避免重复渲染：用 `useId()` 或 props.messageIndex + part.index 组合

### ChatInput.vue

```
Props:
  loading: boolean

Emits:
  'send': text: string
  'upload': file: File
```

布局与现有 `.agent-input` 保持一致。

### FloatingButton.vue

```
Props: (none)
Emits: 'click'
```

包含 useDrag composable，position 由 internal state 管理。

## 数据流

```
useChatSession         useChatStream          useChatMessages
  │ sessions               │ loading               │ messages
  │ sessionId              │ error                 │ copy/regenerate
  │ refreshSessions()      │ streamEvents()        │
  │ createSession()        │ cancelStream()        │
  │ switchSession()        │                       │
  │ deleteSession()        │                       │
  └──────┬─────────────────┴───────────┬───────────┘
         │                             │
         └────────── ChatView ─────────┘
```

- 无 Pinia store，所有状态在 composable 中，实例化于 ChatView
- ChatView 通过 provide/inject 向下传递关键状态给子组件
- SSE streaming 通过 `useChatStream.streamEvents()` 回调直接修改 messages reactive 数组

## 不变的部分

以下模块和 API 完全不动：
- `web/src/api/agent.ts` — 所有 Agent API 函数签名不变
- `streamEvents()` — 7 参数回调签名不变
- `marked`, `mermaid`, `echarts` 渲染逻辑 — 原样迁移
- Element Plus 依赖 — 继续使用 `el-button`, `el-dropdown` 等
- `AppLayout.vue` 中的 `<AgentChat />` 挂载点不变

## 迁移策略

1. **不破坏现有功能** — 每个步骤完成后可独立验证
2. **自底向上** — 先建最底层组件（ChatContent, ChatToolCall），逐层向上组合
3. **每个组件完成后替换 AgentChat.vue 中对应的代码块**
4. **最终 AgentChat.vue 退化为纯编排层**

## 风险

- ChatContent 中 ECharts/Mermaid 的 DOM ID 管理需注意：现有代码用 Math.random() 生成 ID，拆分后需保证全局唯一
- useChatStream 的 AbortController 生命周期需要在 ChatView onUnmounted 中清理
- 文件上传的 FormData 处理保持现有逻辑不变
