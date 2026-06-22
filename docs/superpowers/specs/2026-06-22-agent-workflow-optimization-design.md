# Agent 工艺参数调优工作流 — 设计文档

**日期**: 2026-06-22
**目标**: 将 Agent 从被动响应式改造为主动引导式，按 5 阶段工艺参数调优流程（Define → Explore → Analyze → Optimize → Verify）推进对话。

## 1. 设计决策

- **方案**: Supervisor 流程化 + 前端流程向导，两者结合
- **数据传递**: 混合模式 — 结构化小数据（goal/baseline/recommendation）存 State，大数据通过 `dataset_id`/`experiment_plan_id` 引用
- **路由**: Supervisor 新增 `workflow` 模式；Worker 统一用一个增强 worker，按 phase 切换 system prompt

## 2. AgentState 新增字段

```python
class AgentState(TypedDict):
    # === 现有字段 ===
    messages: Annotated[list, add_messages]
    user_id: str
    process_type: str
    intent: str
    next: str

    # === 新增：调优工作流 ===
    mode: str              # "chat" | "workflow"
    phase: str             # "define"|"explore"|"analyze"|"optimize"|"verify"|""

    # 结构化小数据
    goal: dict | None      # {"target_metric":..., "direction":..., "usl":..., "lsl":..., "target_value":...}
    baseline: dict | None  # {"current_cpk":..., "current_params":{...}, "spc_summary":...}
    recommendation: dict | None  # {"params":{...}, "predicted_cpk":..., "model_r2":...}

    # 大数据引用
    dataset_id: str        # Explore 阶段构建
    experiment_plan_id: int  # DOE 方案 ID
```

## 3. Supervisor 路由增强

### 3.1 模式检测

Supervisor 在每次路由时检测是否应进入 workflow 模式：

- 用户消息包含优化/调优/改善/提高/降低 + 质量指标 → 自动进入 workflow 模式
- 用户在前端点击"工艺调优"快捷按钮 → 前端发送 `__start_workflow__` 消息
- 用户说"退出调优"/"换个话题" → 退回 chat 模式

### 3.2 阶段推进逻辑

```
Supervisor (workflow 模式):
  if phase == "":
      route → analyzer (define prompt)
  elif phase == "define" and 产出 goal + baseline:
      phase = "explore"
  elif phase == "explore" and 产出 dataset_id or experiment_plan_id:
      phase = "analyze"
  elif phase == "analyze" and 产出分析结果:
      phase = "optimize"
  elif phase == "optimize" and 产出 recommendation:
      phase = "verify"
  elif phase == "verify" and 用户确认:
      phase = ""  → FINISH
```

阶段推进由 Supervisor LLM 判断（结构化输出 `PhaseDecision`），而非硬编码规则：

```python
class PhaseDecision(BaseModel):
    action: Literal["STAY", "ADVANCE", "BACK", "FINISH"]
    reason: str
```

### 3.3 SupervisorDecision 更新

```python
class SupervisorDecision(BaseModel):
    intent: Literal["CHAT", "ANALYZER", "RECOMMENDER", "TOOLS", "FINISH"]
    # 新增：workflow 模式下可选
    phase_action: Literal["STAY", "ADVANCE", "BACK", "FINISH"] | None = None
```

## 4. Worker 五阶段 System Prompt

Worker 在 workflow 模式下接收阶段专属 prompt，引导 LLM 按标准流程操作：

### Phase 1 — Define（明确目标与基准）

```
你是工艺参数调优专家，当前处于「明确目标与基准」阶段。

## 任务
1. 引导用户明确：优化哪个质量指标？方向（最大化/最小化/达标）？
2. 调用 get_process_knowledge 获取工艺规范（USL/LSL）
3. 调用 get_latest_active_parameters 获取当前参数作为基准
4. 调用 run_spc 获取当前 Cpk 基线
5. 汇总为「优化目标卡」表格

## 输出格式
| 项目 | 内容 |
|------|------|
| 优化目标 | 剪切强度 ↑ |
| USL / LSL | N/A / 80 kgf/cm² |
| 当前 Cpk | 0.82 |
| 当前参数 | 固化温度 145°C, 固化时间 45min, ... |
```

### Phase 2 — Explore（设计试验与探索）

```
当前处于「设计试验与探索」阶段。

## 任务
1. 若历史数据 ≥ 30条：build_dataset → profile_data → analyze_pareto
2. 若数据不足：引导用户设计 DOE（design_experiment），建议 Box-Behnken 或 Central Composite
3. 若设计了实验：提示用户按实验矩阵执行并记录结果

## 输出
- 数据集 ID 或实验方案 ID
```

### Phase 3 — Analyze（数据分析与建模）

```
当前处于「数据分析与建模」阶段。

## 任务
1. 基于 Phase 2 的 dataset_id，执行：
   - analyze_correlation（相关性矩阵）
   - analyze_importance（特征重要性排序）
   - run_regression（回归建模，输出 R² 和系数）
2. 若有 DOE 数据：analyze_experiment（ANOVA 方差分析）
3. 识别关键因子，评估模型质量

## 输出
- 关键因子排名表
- 回归模型摘要（R², RMSE, 显著因子）
```

### Phase 4 — Optimize（训优与参数推荐）

```
当前处于「训优与参数推荐」阶段。

## 任务
1. 调用 recommend_params 或 optimize_parameters（多目标）
2. 自动传入 Phase 1 的 goal 约束
3. 调用 get_process_knowledge 校验工艺规则
4. 对比推荐参数 vs 当前基准

## 输出格式
| 参数 | 当前值 | 推荐值 | 调整 |
|------|--------|--------|------|
| 固化温度 | 145°C | 152°C | +7°C |
| ... | ... | ... | ... |

- 预测 Cpk: 0.82 → 1.45
- 风险提示
```

### Phase 5 — Verify（验证与闭环）

```
当前处于「验证与闭环」阶段。

## 任务
1. 汇总整个调优过程的产出
2. 建议用户：提交审批（submit_parameter_set）→ 试验验证 → SPC 持续监控
3. 若用户不满意推荐结果：可回退到 Explore/Analyze/Optimize 阶段

## 输出格式
- 调优前后对比表
- 下一步操作建议
```

## 5. SSE 事件扩展

在 `agent_routes.py` 的 `_map_event()` 中新增 `phase.change` 事件：

```python
# 当 phase 推进时，前端收到此事件更新进度条
{
    "type": "phase.change",
    "phase": "explore",
    "prev_phase": "define",
    "goal": {...},
    "baseline": {...}
}
```

## 6. 前端改动

### 6.1 流程指示器 (PhaseIndicator.vue)

位置：AgentHeader 下方，仅 workflow 模式显示。

```
● Define ──→ ● Explore ──→ ○ Analyze ──→ ○ Optimize ──→ ○ Verify
             当前：探索数据与设计实验
```

- 已完成阶段：实心绿点 + 可点击查看摘要
- 当前阶段：脉冲动画高亮
- 未开始阶段：空心灰点

### 6.2 快捷按钮 (ChatInput.vue toolbar)

工具栏新增「工艺调优」按钮（魔棒图标），点击发送 `__start_workflow__`。

### 6.3 ChatView.vue 集成

```html
<PhaseIndicator v-if="workflowPhase" :phase="workflowPhase" />
<ChatBubble ... />
<ChatInput ... >
  <!-- toolbar 中新增快捷按钮 -->
</ChatInput>
```

## 7. 文件变更清单

| 文件 | 操作 | 内容 |
|---|---|---|
| `src/process_opt/agent/state.py` | 修改 | 新增 6 个 workflow 字段 |
| `src/process_opt/agent/nodes/supervisor.py` | 修改 | 新增 workflow 模式检测 + PhaseDecision + 阶段路由 |
| `src/process_opt/agent/nodes/worker.py` | 修改 | ROLE_PROMPTS 新增 5 个阶段 prompt |
| `src/process_opt/api/agent_routes.py` | 修改 | SSE 新增 `phase.change` 事件 |
| `web/src/components/agent/PhaseIndicator.vue` | 新建 | 流程进度指示器 |
| `web/src/components/agent/ChatView.vue` | 修改 | 集成 PhaseIndicator |
| `web/src/components/agent/ChatInput.vue` | 修改 | toolbar 新增快捷按钮 |
| `web/src/composables/useChatStream.ts` | 修改 | 处理 `phase.change` 事件 |
| `web/src/composables/useChatMessages.ts` | 修改 | 新增 phase 状态 |

## 8. 测试策略

- `tests/agent/test_workflow_routing.py` — 测试 Supervisor 模式检测和阶段推进
- `tests/agent/test_phase_prompts.py` — 验证各阶段 prompt 包含必要指令
- 前端手动验证 — 流程指示器显示、阶段切换 SSE 事件
