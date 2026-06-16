# Agent 系统设计（Code-as-Action）

## 概述

Agent 根据用户自然语言指令，由 LLM 动态生成 Python 代码并在沙箱中执行，实现无限可扩展的分析能力。执行成功的代码可沉淀为可复用 Skill。

## 执行流程

```
用户 → LLM 规划 → 生成 Python → 沙箱执行 → 结果 → LLM 解读 → 回复
                            ↑ 失败则迭代修正
```

## 组件设计

### Backend

| 文件 | 职责 |
|------|------|
| `agent/schemas.py` | AgentChatRequest, AgentChatResponse, ExecutionResult |
| `agent/sandbox.py` | 代码沙箱：tempdir + subprocess + timeout + 依赖注入 |
| `agent/executor.py` | LLM 编排：system prompt → code gen → exec → feedback loop |
| `agent/service.py` | AgentService Protocol + SSE 流式端点 |
| `agent/db.py` | 沙箱内可用的数据库查询辅助 |

### Frontend

| 文件 | 职责 |
|------|------|
| `api/agent.ts` | SSE 流式客户端 |
| `components/AgentChat.vue` | 聊天面板（消息列表 + 输入 + tool call 可视化） |
| `AppLayout.vue` | 替换 iframe 为原生 AgentChat 面板 |

### 关键设计决策

**沙箱安全：**
- 沙箱使用隔离 `tempfile.mkdtemp()` 作为工作目录
- 超时控制（默认 30s）
- 注入数据库连接（通过代码前置注入 `import` 语句）
- 仅允许标准库 + 已安装的科学计算包
- 执行结果通过 stdout JSON 输出

**LLM 交互模式：**
- System Prompt 注入可用库（numpy, scipy, sklearn, 自定义 helper）
- Code Generation：LLM 输出完整的 Python 脚本
- 执行后，将 stdout + stderr + 返回值反馈给 LLM
- LLM 迭代修复代码错误（最多 3 次重试）

**Skill 沉淀（后续扩展）：**
- 成功执行的代码以 hash 为 key 入库
- 用户可手动标记为 Skill
- 后续类似任务可匹配到已有 Skill
