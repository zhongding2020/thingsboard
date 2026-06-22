# Chat UI 重设计 — 设计方案

> 对比 deepagents-ui，将现有 Vue 3 Chat UI 升级为具备子智能体可视化、按工具类型渲染、文件查看器、Todo 面板、线程选择器、streamdown 动画、Debug 模式和深色/浅色主题的现代对话界面。

**状态:** 设计完成，待实现

**技术栈:** Vue 3 + Tailwind CSS + Element Plus + Pinia + Vite + TypeScript + `@langchain/vue` SDK

---

## 方案选择

**方案 A（选择）：渐进式替换**

核心思路：SDK 先换，组件逐个追平 feature set。分 4 个 Phase 独立交付，每 Phase 可独立测试和上线。

- 引入 `@langchain/vue`（`useStream` / `useMessages` / `useToolCalls`）替代自研 composables
- 引入 Tailwind CSS，与 Element Plus 共存（加 `prefix: 'tw-'` 隔离）
- 按优先级分批交付：SDK 迁移 + streamdown → 子智能体 + 工具渲染器 → 文件查看器 + Todo → 线程选择器 + Debug + 主题
- 现有 9 个业务页面、路由结构完全不动

**被排除的方案：**
- 方案 B（全量重写）：工期长、风险高，一次性切换有回归风险
- 方案 C（iframe 嵌入）：集成体验差，主题不同步，路由割裂

---

## Section 1: 架构总览

### 数据流变化

```
当前（自研 composables）:
  SSE events → agent.ts (fetch + ReadableStream) → useChatStream (回调) → useChatMessages (手动 push parts[]) → 组件

方案 A（@langchain/vue SDK）:
  SSE events → useAgentStream (薄适配器) → @langchain/vue useStream() → reactive Message[] (含 tool_calls, subagents, todos 等标准字段) → 组件
```

### 组件树映射

```
deepagents-ui (React)              →  方案 A (Vue 3)
─────────────────────────────────────────────────────
ThreadPicker                       →  ThreadPicker（SessionList 升级）
AgentChat (主容器)                  →  ChatView（重构）
  MessageList                       →  （内联在 ChatView）
    MessageCard                     →  MessageCard（重构自 ChatBubble + ChatToolCall）
      SubagentCard                  →  SubagentCard（新增）
      ToolCallCard                  →  ToolCallCard（重构自 ChatToolCall）
        FilesRenderer               →  FilesRenderer（新增）
        SearchRenderer              →  SearchRenderer（新增）
        ThinkRenderer               →  ThinkRenderer（新增）
        TodosRenderer               →  TodosRenderer（新增）
  FilesystemPanel                   →  FilesystemDrawer（新增）
  TodoPanel                         →  TodoDrawer（新增）
ChatInput                           →  ChatInput（升级）
```

---

## Section 2: SDK 迁移方案

### 后端改动

后端 SSE 格式保持现有 6 种事件类型不变。新增 4 种事件以支持子智能体和 Todo：

```
现有事件（不变）:
  message.delta    ← on_chat_model_stream
  tool.call        ← on_tool_start
  tool.result      ← on_tool_end
  node.start       ← on_chain_start
  node.end         ← on_chain_end
  thinking.*       ← 自定义
  suggestions      ← 自定义

新增事件:
  subagent.start   ← on_chain_start (当 event name 以 "subagent:" 开头时)
  subagent.delta   ← on_chat_model_stream (嵌套子智能体的 token 流)
  subagent.end     ← on_chain_end   (当 event name 以 "subagent:" 开头时)
  todo.update      ← 从 agent state 周期性提取 emit
```

改动集中在 `src/process_opt/api/agent_routes.py:_map_event()`，约 +30 行。

### 前端替换

```
删除                              新增 / 替换
─────────────────────────────────────────────────────
api/agent.ts (SSE 解析, ~70行) →  api/agent.ts (精简为 REST only)
useChatStream.ts (全部)         →  composables/useAgentStream.ts (~60行 适配器)
useChatMessages.ts (全部)       →  @langchain/vue useMessages()
```

**适配层设计：**

```typescript
// composables/useAgentStream.ts
// 包装 @langchain/vue 的 useStream，适配我们的 SSE 格式
// 将自定义 SSE 事件转换为 LangChain 标准 streaming events
// 降级策略：如果 @langchain/vue 版本对自定义 stream 支持不足，
// 则 useMessages 管状态 + 保留轻量 SSE parser，效果等同
```

### 对比

| | 当前 | 方案 A 后 |
|---|---|---|
| SSE 解析代码 | `agent.ts` 70 行 + `useChatStream.ts` 70 行 | `useAgentStream.ts` ~60 行（适配器） |
| 消息状态管理 | `useChatMessages.ts` 70 行（手动 push parts[]） | `useMessages()` SDK 内置 |
| 工具调用状态 | 内联在 parts[] 中 | `useToolCalls()` 响应式提取 |
| 可维护性 | 自研，需自行处理边界 | 官方 SDK 维护 |

---

## Section 3: 组件树 & Phase 分发

### 完整组件树

```
ChatView.vue (重构 — 主容器，flex 布局，左 chat / 右面板)
├── ThreadPicker (SessionList 升级)
│   ├── 自动标题生成（首条消息摘要）
│   ├── 搜索 / 过滤
│   └── 置顶 / 归档
│
├── MessageList (虚拟滚动，自动 scroll-to-bottom)
│   └── MessageCard.vue (重构自 ChatBubble + ChatToolCall)
│       ├── TextBlock.vue        — Markdown + streamdown 逐字动画
│       ├── ThinkingBlock.vue    — 可折叠 <details>，保留现有逻辑
│       ├── ToolCallCard.vue     — 工具调用卡片容器
│       │   ├── FilesRenderer    — 表格 / 文件列表预览
│       │   ├── SearchRenderer   — 搜索结果高亮
│       │   ├── ThinkRenderer    — 思维过程折叠
│       │   └── TodosRenderer    — 内联 todo 勾选
│       └── SubagentCard.vue     — 【新增】子智能体卡片
│           ├── 可折叠 / 可调高度
│           ├── 实时流式子输出
│           └── 状态指示 (running / done / error)
│
├── ChatInput.vue (保留升级)
│   ├── 文本输入 + 发送/停止
│   ├── 工艺向导（保留）
│   └── 文件上传（保留）
│
├── FilesystemDrawer.vue   — 【新增】右侧抽屉，文件树 + 代码高亮
├── TodoDrawer.vue         — 【新增】右侧抽屉，todo 列表 + 复选框
├── DebugPanel.vue         — 【新增】底部面板，执行步骤回放
└── PhaseIndicator.vue     — 保留，升级样式
```

### Phase 分发

| Phase | 内容 | 交付物 | 工期 |
|---|---|---|---|
| **P1: 基础层** | ① Tailwind 引入 + 配置 ② `@langchain/vue` SDK 迁移 ③ MessageCard + streamdown 动画 ④ ToolCallCard 基础重构 | SDK 替换完成，UI 行为不变 | ~1 周 |
| **P2: 核心 Feature** | ① SubagentCard（后端 + `subagent.*` 事件）② 4 个 Per-Tool Renderer ③ Todo 后端事件 | 子智能体可视化 + 工具渲染可用 | ~1 周 |
| **P3: 辅助面板** | ① FilesystemDrawer ② TodoDrawer ③ ThreadPicker（SessionList 升级） | 文件查看 + Todo + 线程选择 | ~0.5 周 |
| **P4: 体验层** | ① DebugPanel ② 深色/浅色主题 ③ 打磨 | 主题 + Debug | ~0.5 周 |

**总计 ~3 周。** 每个 Phase 独立测试、独立上线，P1 上线即可获得 SDK 迁移收益。

---

## Section 4: 样式策略 & 路由设计

### Tailwind + Element Plus 共存

```
安装: tailwindcss @tailwindcss/vite
配置: tailwind.config.js 中 prefix: 'tw-'

类名示例:
  Element Plus:  <el-button type="primary">     （业务页面不动）
  Tailwind:      <div class="tw-flex tw-gap-4">  （chat 区域专用）
```

**主题同步：**
- Tailwind `dark:` 变体 + CSS 自定义属性
- 一个 `useTheme` composable 统一切换：`document.documentElement.classList.toggle('dark')`
- Element Plus 暗色模式通过其内置机制同步触发

### 路由

```
现有（保留）:
  / → AppLayout → 9 个业务页面
  FloatingButton → ChatView 全屏浮层（z-index 覆盖）

新增（Phase 4 可选）:
  /chat  →  独立全页 ChatView（用于 Debug 模式、大屏场景）
```

### 文件组织

```
web/src/
├── components/agent/
│   ├── ChatView.vue              # 重构
│   ├── MessageCard.vue           # 新增（ChatBubble + ChatToolCall 合并升级）
│   ├── SubagentCard.vue          # 新增
│   ├── renderers/                # 新增目录
│   │   ├── FilesRenderer.vue
│   │   ├── SearchRenderer.vue
│   │   ├── ThinkRenderer.vue
│   │   └── TodosRenderer.vue
│   ├── panels/                   # 新增目录
│   │   ├── FilesystemDrawer.vue
│   │   ├── TodoDrawer.vue
│   │   └── DebugPanel.vue
│   ├── ThreadPicker.vue          # SessionList 升级
│   ├── ChatInput.vue             # 升级
│   ├── PhaseIndicator.vue        # 升级样式
│   ├── AgentHeader.vue           # 保留升级
│   ├── AgentSidebar.vue          # 保留
│   ├── ChatContent.vue           # 保留
│   ├── ChatSuggestions.vue       # 保留
│   └── FloatingButton.vue        # 保留
│
├── composables/
│   ├── useAgentStream.ts         # 新增，替代 useChatStream + agent.ts SSE
│   ├── useTheme.ts               # 新增
│   ├── useChatSession.ts         # 保留升级
│   ├── useDrag.ts                # 保留
│   └── useFileUpload.ts          # 保留
│
└── api/
    └── agent.ts                  # 精简，仅 REST（创建会话、历史消息等）
```

### 删除清单

| 文件 | 原因 |
|---|---|
| `useChatStream.ts` | 被 `useAgentStream.ts` + `@langchain/vue` 替代 |
| `useChatMessages.ts` | 被 `@langchain/vue` `useMessages()` 替代 |
| `agent.ts` SSE 解析部分 (~70行) | 移到 `useAgentStream.ts` 适配层 |
| `ChatToolCall.vue` | 合并到 `MessageCard.vue` |
| `ChatBubble.vue` | 合并到 `MessageCard.vue` |
| `ChatLoading.vue` | 用 Tailwind skeleton 替代 |

---

## 风险与降级策略

| 风险 | 降级 |
|---|---|
| `@langchain/vue` 对自定义 SSE stream 支持不足 | 仅用 `useMessages` 管状态 + 保留轻量 SSE parser，效果等同 |
| Tailwind 与 Element Plus 样式冲突 | `prefix: 'tw-'` 完全隔离，任何冲突只影响单组件 |
| Subagent 嵌套流在后端不可用 | `subagent.*` 事件为 optional，前端 graceful fallback 到 `node.*` 事件 |
| 虚拟滚动在消息列表中引入 bug | MessageList 先用简单 `v-for`，Phase 4 再加虚拟滚动优化 |

---

## 成功标准

1. **P1 完成:** SDK 迁移后，现有所有功能不变（发消息、流式输出、工具调用、thinking、建议问题、工艺向导、文件上传）
2. **P2 完成:** 子智能体卡片可折叠/展开，实时流式输出；4 种工具渲染器按工具名称自动匹配
3. **P3 完成:** 文件查看器可浏览文件树并查看文件内容；Todo 列表与 agent state 实时同步；线程选择器支持搜索和自动标题
4. **P4 完成:** Debug 模式可逐步查看执行步骤；深色/浅色主题一键切换
5. **全部 Phase:** 现有 9 个业务页面功能不受影响
