# Agent 系统优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 9 项 agent 系统优化，覆盖规则校验、代码去重、bug 修复、算法升级、输出格式、错误处理、数据持久化

**Architecture:** 按复杂度分 3 阶段执行：Phase 1 低复杂度 (Supervisor/工具提取/错误处理/RuleEngine) → Phase 2 中复杂度 (Worker工厂/ANOVA/LHS/Markdown) → Phase 3 高复杂度 (DOE replicates/数据集持久化)

**Tech Stack:** Python 3.11, LangGraph, scipy, sklearn, PostgreSQL, pydantic

---

## Phase 1: 低复杂度优化

### Task 1: Supervisor 改为 with_structured_output

**Files:**
- Modify: `src/process_opt/agent/nodes/supervisor.py`

- [ ] **Step 1: Rewrite supervisor.py**

Replace the string-matching routing with pydantic structured output:

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Literal

from process_opt.agent.state import AgentState


class SupervisorDecision(BaseModel):
    intent: Literal["CHAT", "ANALYZER", "RECOMMENDER", "FINISH"]


def create_supervisor_node(llm: BaseChatModel):
    structured_llm = llm.with_structured_output(SupervisorDecision, method="function_calling")

    async def supervisor_node(state: AgentState) -> dict:
        last_human = None
        last_assistant = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage) and last_human is None:
                last_human = msg
            elif hasattr(msg, "type") and msg.type == "ai" and last_assistant is None:
                last_assistant = msg

        ctx = ""
        if last_human:
            ctx += f"用户消息: {last_human.content}\n"
        if last_assistant:
            content = last_assistant.content
            if isinstance(content, list):
                content = " ".join(
                    t.get("text", "") if isinstance(t, dict) else str(t)
                    for t in content
                )
            ctx += f"助手已回复: {str(content)[:200]}\n"

        prompt = (
            "根据对话状态输出下一个处理节点。\n\n"
            "- CHAT: 通用问答、工艺咨询\n"
            "- ANALYZER: 数据分析（SPC、相关性、回归等）\n"
            "- RECOMMENDER: 参数推荐或优化\n"
            "- FINISH: 本轮对话已完成，助手已给出实质性回答\n\n"
            f"{ctx}"
        )

        result: SupervisorDecision = await structured_llm.ainvoke([SystemMessage(content=prompt)])
        intent = result.intent.upper()
        if intent == "FINISH":
            return {"next": "FINISH"}
        return {"next": intent.lower()}

    return supervisor_node
```

- [ ] **Step 2: Verify**

```bash
cd /Users/zhongding/dev/thingsboard && python -c "from process_opt.agent.nodes.supervisor import create_supervisor_node; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/nodes/supervisor.py
git commit -m "refactor: supervisor uses with_structured_output for reliable routing"
```

---

### Task 2: _extract_arrays 提取到共享 utils

**Files:**
- Create: `src/process_opt/analysis/utils.py`
- Modify: `src/process_opt/analysis/correlation.py` (replace import of _extract_arrays)
- Modify: `src/process_opt/analysis/regression.py` (same)
- Modify: `src/process_opt/analysis/recommendation.py` (same)
- Modify: `src/process_opt/analysis/importance.py` (same)
- Modify: `src/process_opt/analysis/optimization.py` (same)

- [ ] **Step 1: Create analysis/utils.py**

```python
from __future__ import annotations

import numpy as np

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset


def extract_arrays(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
) -> tuple[np.ndarray, np.ndarray]:
    n = dataset.sample_count
    if n == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot compute on empty dataset",
        )

    feat_cols: list[list[float]] = [[] for _ in feature_fields]
    tgt_vals: list[float] = []

    for i in range(n):
        for j, field in enumerate(feature_fields):
            v = dataset.features[i].get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Field '{field}' contains non-numeric or missing values",
                )
            feat_cols[j].append(float(v))
        v = dataset.targets[i].get(target_field)
        if v is None or not isinstance(v, (int, float)):
            raise AnalysisError(
                code="NON_NUMERIC_FIELD",
                message=f"Target field '{target_field}' contains non-numeric or missing values",
            )
        tgt_vals.append(float(v))

    X = np.column_stack([np.array(col, dtype=np.float64) for col in feat_cols])
    y = np.array(tgt_vals, dtype=np.float64)
    return X, y
```

- [ ] **Step 2: Update 5 files to import from utils**

For each of `correlation.py`, `regression.py`, `importance.py`, `optimization.py`, and `recommendation.py`:

Remove the local `_extract_arrays` function definition. Replace the import at the top with:

```python
from process_opt.analysis.utils import extract_arrays
```

Then update all `_extract_arrays(...)` calls to `extract_arrays(...)`.

For each file:
```bash
# Example for correlation.py: find the _extract_arrays function and its callers
grep -n "_extract_arrays" src/process_opt/analysis/correlation.py
```

- [ ] **Step 3: Verify all imports work**

```bash
cd /Users/zhongding/dev/thingsboard && python -c "from process_opt.analysis.utils import extract_arrays; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/analysis/utils.py src/process_opt/analysis/correlation.py src/process_opt/analysis/regression.py src/process_opt/analysis/recommendation.py src/process_opt/analysis/importance.py src/process_opt/analysis/optimization.py
git commit -m "refactor: extract shared _extract_arrays to analysis/utils.py"
```

---

### Task 3: 错误处理增强 (SUGGESTIONS 补全 + 工具重试装饰器)

**Files:**
- Modify: `src/process_opt/api/app.py` (completion of SUGGESTIONS mapping)
- Create: `src/process_opt/agent/tools/retry.py` (retry decorator)
- Modify: `src/process_opt/agent/tools/analysis_tools.py` (apply @with_retry to DB/compute tools)

- [ ] **Step 1: Complete SUGGESTIONS in app.py**

Replace the existing `_SUGGESTIONS` dict (around line 106) with:

```python
_SUGGESTIONS: dict[str, str] = {
    "NOT_FOUND": "Check the ID parameter and try again. The resource may have been deleted.",
    "INVALID_TRANSITION": "Check allowed transitions: draft->proposed, proposed->approved, proposed->rejected, approved->active.",
    "INVALID_PARAMS": "Check the request parameters. Ensure all required fields are provided and valid.",
    "DATASET_NOT_FOUND": "Build or upload a dataset first. The dataset may have expired.",
    "DEVICE_NOT_FOUND": "Check the device_id. List available devices with GET /devices.",
    "RECORD_NOT_FOUND": "No data found for the given query. Check barcode or filters.",
    "NO_DATA": "No data available for the specified filters. Try a wider time range.",
    "TOO_FEW_POINTS": "At least 5 data points are required for this analysis. Upload more data.",
    "COMPUTATION_FAILED": "Analysis computation failed. Check data quality for missing or invalid values.",
    "FEATURE_MISMATCH": "Feature fields do not match the dataset columns. Check field names.",
}
```

- [ ] **Step 2: Create retry decorator**

```python
# src/process_opt/agent/tools/retry.py
from __future__ import annotations

import functools
import logging

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 1):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning("Tool %s retry %d/%d: %s", func.__name__, attempt + 1, max_retries, e)
            raise last_error
        return wrapper
    return decorator
```

- [ ] **Step 3: Apply @with_retry to DB/compute tools in analysis_tools.py**

Add `from process_opt.agent.tools.retry import with_retry` at the top of analysis_tools.py.

Then add `@with_retry()` decorator to:
- `query_records` — DB query
- `get_stats` — DB stats
- `trace_product` — DB trace
- `analyze_correlation` — computation
- `run_regression` — computation
- `run_spc` — computation
- `recommend_params` — computation

Example:
```python
@tool
@with_retry()
async def query_records(device_id: str = "", page: int = 1, page_size: int = 20) -> str:
    ...
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/api/app.py src/process_opt/agent/tools/retry.py src/process_opt/agent/tools/analysis_tools.py
git commit -m "feat: complete SUGGESTIONS mapping + @with_retry decorator for agent tools"
```

---

### Task 4: RuleEngine 接入 recommend 工具

**Files:**
- Modify: `src/process_opt/agent/tools/analysis_tools.py` (recommend_params tool)

- [ ] **Step 1: Add rule validation to recommend_params**

In `analysis_tools.py`, inside the `recommend_params` tool function, after computing the recommendation result, add rule checking:

Add imports at the top of the function (inside the tool closure):
```python
from process_opt.knowledge.loader import KnowledgeLoader
from process_opt.knowledge.rules import RuleEngine
```

After the `result = service.compute_recommendation(...)` line, add:
```python
# Validate recommended params against process rules
rule_violations = []
try:
    loader = KnowledgeLoader()
    template = loader.load(process_type) if process_type else None
    if template and template.rules:
        engine = RuleEngine()
        checks = engine.check_params(template, result.recommended_parameters)
        warnings = engine.get_violations(checks, "warning")
        errors = engine.get_violations(checks, "hard")
        for v in errors:
            rule_violations.append(f"❌ 违规: {v.message}")
        for v in warnings:
            rule_violations.append(f"⚠ 警告: {v.message}")
except Exception:
    pass

# Build Markdown output with rule status
parts = [
    f"## 参数推荐结果",
    f"**模型 R²**: {result.model_metrics.get('r_squared', 'N/A'):.4f}",
    f"**目标值**: {request.target_value} | **预测值**: {result.predicted_target:.2f}",
    f"",
    f"### 推荐参数",
    f"| 参数 | 推荐值 |",
    f"|------|--------|",
]
for k, v in result.recommended_parameters.items():
    parts.append(f"| {k} | {v:.2f} |")

if result.alternatives:
    parts.append(f"\n### 备选方案")
    parts.append(f"| # | 参数组合 |")
    parts.append(f"|---|----------|")
    for i, alt in enumerate(result.alternatives[:5]):
        parts.append(f"| {i+1} | {', '.join(f'{k}={v:.2f}' for k,v in alt.items())} |")

if rule_violations:
    parts.append(f"\n### 规则校验")
    parts.extend(rule_violations)
else:
    parts.append(f"\n✅ 所有推荐参数符合工艺规则。")

if result.risk_notes:
    parts.append(f"\n### 风险提示")
    for note in result.risk_notes:
        parts.append(f"- {note}")

return "\n".join(parts)
```

**Note:** The `recommend_params` tool needs `process_type` available. Check how it accesses the state — if needed, inject `process_type` as a tool parameter or extract from session context.

Additionally, update `_infer_bounds` in `recommendation.py` to use the full range (don't error on SEARCH_SPACE_TOO_LARGE — see Task 7 LHS).

- [ ] **Step 2: Verify**

```bash
cd /Users/zhongding/dev/thingsboard && python -c "from process_opt.knowledge.rules import RuleEngine; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/analysis_tools.py
git commit -m "feat: integrate RuleEngine into recommend_params tool with Markdown output"
```

---

## Phase 2: 中复杂度优化

### Task 5: Worker 节点工厂化重构

**Files:**
- Create: `src/process_opt/agent/nodes/worker.py`
- Modify: `src/process_opt/agent/graph.py` (use new factory)
- Delete: `agent/nodes/chat.py`, `agent/nodes/analyzer.py`, `agent/nodes/recommender.py`

- [ ] **Step 1: Create factory worker.py**

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


ROLE_PROMPTS = {
    "chat": {
        "title": "工艺参数分析助手",
        "instructions": "用中文回答，使用 Markdown 格式。数据分析结果用表格呈现。",
    },
    "analyzer": {
        "title": "工艺数据分析专家",
        "instructions": "任务: 1.选择合适分析工具 2.调用工具获取结果 3.用中文解读 4.用表格呈现 5.不输出原始JSON",
    },
    "recommender": {
        "title": "工艺参数推荐专家",
        "instructions": "任务: 1.build_dataset构建数据集 2.run_regression分析 3.recommend_params推荐 4.结合规则过滤 5.用表格呈现",
    },
}


def create_worker_node(role: str, llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    if role not in ROLE_PROMPTS:
        raise ValueError(f"Unknown role: {role}. Valid: {list(ROLE_PROMPTS.keys())}")

    role_cfg = ROLE_PROMPTS[role]

    async def worker_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""
        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}{role_cfg['title']}。\n\n"
                f"{knowledge_prompt}\n\n"
                f"{role_cfg['instructions']}"
            )
        )
        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return worker_node
```

- [ ] **Step 2: Update graph.py**

Replace the old imports:
```python
from process_opt.agent.nodes.chat import create_chat_node
from process_opt.agent.nodes.analyzer import create_analyzer_node
from process_opt.agent.nodes.recommender import create_recommender_node
```
With:
```python
from process_opt.agent.nodes.worker import create_worker_node
```

Replace the node creation calls:
```python
chat_node = create_chat_node(llm, knowledge_loader)
analyzer_node = create_analyzer_node(llm, knowledge_loader)
recommender_node = create_recommender_node(llm, knowledge_loader)
```
With:
```python
chat_node = create_worker_node("chat", llm, knowledge_loader)
analyzer_node = create_worker_node("analyzer", llm, knowledge_loader)
recommender_node = create_worker_node("recommender", llm, knowledge_loader)
```

- [ ] **Step 3: Delete old files**

```bash
rm src/process_opt/agent/nodes/chat.py src/process_opt/agent/nodes/analyzer.py src/process_opt/agent/nodes/recommender.py
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/zhongding/dev/thingsboard && docker-compose build backend-api 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/agent/nodes/worker.py src/process_opt/agent/graph.py
git rm src/process_opt/agent/nodes/chat.py src/process_opt/agent/nodes/analyzer.py src/process_opt/agent/nodes/recommender.py
git commit -m "refactor: replace 3 worker nodes with single factory create_worker_node(role)"
```

---

### Task 6: ANOVA 使用实际设计矩阵

**Files:**
- Modify: `src/process_opt/agent/tools/analysis_tools.py` (analyze_experiment tool, ~line 200-230)
- Modify: `src/process_opt/analysis/doe_service.py` (run_anova: accept actual design matrix)

- [ ] **Step 1: Fix analyze_experiment tool**

In `analysis_tools.py`, replace the hardcoded full-factorial generation (lines ~200-228) with code that extracts factor values from the actual stored design runs:

```python
# Build design matrix from actual stored runs (not hardcoded full factorial)
design_runs: list[Any] = plan.design_runs
factors_list = [DOEFactor(**f) if isinstance(f, dict) else f for f in factors]

req = ANOVARequest(
    factors=factors_list,
    design_runs=[DOERun(
        run_order=r.run_order,
        standard_order=r.standard_order or r.run_order,
        factor_values=r.factor_values,
    ) for r in design_runs],
    results=results,
    response_name=response_name,
)
anova = run_anova(req)
```

- [ ] **Step 2: Verify run_anova accepts actual design matrix**

The current `run_anova` already extracts factor values from `request.design_runs`:
```python
design_matrix = np.array([list(r.factor_values.values()) for r in request.design_runs])
```
This line is correct — it reads from whatever design runs are passed. So no changes needed in doe_service.py itself. The bug was only in analysis_tools.py where it regenerated a hardcoded full factorial.

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/analysis_tools.py
git commit -m "fix: analyze_experiment uses actual stored design runs instead of hardcoded full factorial"
```

---

### Task 7: Latin Hypercube Sampling 推荐算法升级

**Files:**
- Modify: `src/process_opt/analysis/recommendation.py`

- [ ] **Step 1: Add LHS fallback in _generate_grid**

In `recommendation.py`, after the `if total > MAX_GRID_COMBINATIONS:` block, replace the `raise AnalysisError(...)` with LHS sampling:

```python
import numpy as np
from scipy.stats.qmc import LatinHypercube

# ... (existing _generate_grid code up to the total calculation)

if total > MAX_GRID_COMBINATIONS:
    n_samples = 5000
    free_fields = [f for f in feature_fields if f not in fixed]
    d = len(free_fields)
    if d == 0:
        pass  # All parameters fixed, no search needed
    else:
        sampler = LatinHypercube(d=d)
        sample = sampler.random(n=n_samples)
        # Map [0,1] samples to actual ranges
        for i, field in enumerate(free_fields):
            lo, hi = lower[field], upper[field]
            sample[:, i] = lo + sample[:, i] * (hi - lo)
        # Build grid from LHS samples
        grid: list[dict[str, float]] = []
        for j in range(n_samples):
            row: dict[str, float] = dict(fixed)
            for i, field in enumerate(free_fields):
                row[field] = float(sample[j, i])
            grid.append(row)
        return grid

grid: list[dict[str, float]] = []
for combo in itertools.product(*ranges):
    grid.append(dict(zip(names, combo)))
return grid
```

- [ ] **Step 2: Verify scipy LHS is available**

```bash
cd /Users/zhongding/dev/thingsboard && python -c "from scipy.stats.qmc import LatinHypercube; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/analysis/recommendation.py
git commit -m "feat: add Latin Hypercube Sampling fallback when grid exceeds 10k combinations"
```

---

### Task 8: 所有工具输出改为 Markdown

**Files:**
- Modify: `src/process_opt/agent/tools/analysis_tools.py` (8+ tools)

- [ ] **Step 1: Convert key tools to Markdown output**

Replace `json.dumps(...)` returns with Markdown strings in:

1. **profile_data** — Markdown table with stats
2. **analyze_correlation** — Markdown table + ECharts JSON block
3. **run_regression** — Markdown with R², RMSE, coefficients table
4. **analyze_pareto** — Markdown table with factors, contribution %, bar chart ECharts
5. **recommend_params** — (already done in Task 4 above)
6. **run_spc** — Markdown with Cp, Cpk, control limits
7. **design_experiment** — Markdown design matrix table
8. **analyze_experiment** — Markdown ANOVA table
9. **get_process_knowledge** — Markdown with parameter tables
10. **build_dataset** — Keep JSON (it's consumed by other tools programmatically)

Each tool should output something like:
```python
return "\n".join([
    f"## {title}",
    f"**指标**: {value}",
    f"",
    f"| 列1 | 列2 |",
    f"|-----|-----|",
    f"| {v1} | {v2} |",
])
```

For ECharts, wrap in ````echarts` blocks so frontend renders them:
```python
echarts_json = json.dumps({...}, ensure_ascii=False)
return f"{markdown_table}\n\n```echarts\n{echarts_json}\n```\n"
```

- [ ] **Step 2: Verify build**

```bash
cd /Users/zhongding/dev/thingsboard && docker-compose build backend-api 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/analysis_tools.py
git commit -m "feat: convert all agent tool outputs from JSON to Markdown format"
```

---

## Phase 3: 高复杂度优化

### Task 9: DOE replicates 实现

**Files:**
- Modify: `src/process_opt/analysis/doe_service.py` (generate_design function)

- [ ] **Step 1: Implement replicates in generate_design**

In `doe_service.py`, after building the initial `runs` and `design_matrix` lists, add:

```python
# Apply replicates: duplicate the entire design matrix N times
if config.replicates and config.replicates > 1:
    original_runs = list(runs)
    original_matrix = list(design_matrix)
    for rep in range(1, config.replicates):
        for run in original_runs:
            runs.append(DOERun(
                run_order=len(runs) + 1,
                standard_order=run.standard_order,
                factor_values=dict(run.factor_values),
                replicate=rep + 1,
            ))
        design_matrix.extend([list(row) for row in original_matrix])
```

Note: `DOERun` schema may need `replicate` field. Check `doe_schemas.py`:
```python
class DOERun(BaseModel):
    run_order: int
    standard_order: int
    factor_values: dict[str, float]
    replicate: int = 1  # Add this field
```

- [ ] **Step 2: Update run_count in returned DOEDesign**

Change:
```python
return DOEDesign(
    method=config.method,
    factors=config.factors,
    runs=runs,
    run_count=len(runs),  # Was: n_runs — now reflects replicates
    design_matrix=design_matrix,
)
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/analysis/doe_service.py src/process_opt/analysis/doe_schemas.py
git commit -m "feat: implement DOE replicates field in generate_design"
```

---

### Task 10: 数据集 PostgreSQL 持久化

**Files:**
- Modify: `db/init-db.sql` (new datasets table)
- Create: `src/process_opt/analysis/dataset_repo.py`
- Modify: `src/process_opt/analysis/excel.py` (save_dataset → PostgreSQL)
- Modify: `src/process_opt/api/main.py` (register dataset_repo, add cleanup task)

- [ ] **Step 1: Add datasets table to init-db.sql**

```sql
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 minutes'
);
CREATE INDEX IF NOT EXISTS idx_datasets_expires ON datasets (expires_at);
```

- [ ] **Step 2: Create dataset_repo.py**

```python
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from process_opt.analysis.schemas import AnalysisDataset

DEFAULT_TTL_MINUTES = 30


class DatasetRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, dataset: AnalysisDataset, name: str = "", ttl: int = DEFAULT_TTL_MINUTES) -> str:
        data = dataset.model_dump_json()
        expires = datetime.now(timezone.utc) + timedelta(minutes=ttl)
        id_ = str(uuid.uuid4())
        await self.pool.execute(
            "INSERT INTO datasets (id, name, data, created_at, expires_at) VALUES ($1, $2, $3::jsonb, now(), $4)",
            id_, name, data, expires,
        )
        return id_

    async def get(self, dataset_id: str) -> AnalysisDataset | None:
        row = await self.pool.fetchrow(
            "SELECT data FROM datasets WHERE id = $1 AND expires_at > now()", dataset_id
        )
        if row is None:
            return None
        return AnalysisDataset.model_validate_json(row["data"])

    async def purge_expired(self) -> int:
        result = await self.pool.execute("DELETE FROM datasets WHERE expires_at <= now()")
        return int(result.split()[-1]) if result else 0

    async def get_preview(self, dataset_id: str, limit: int = 20) -> list[dict[str, Any]]:
        row = await self.pool.fetchrow(
            "SELECT data FROM datasets WHERE id = $1 AND expires_at > now()", dataset_id
        )
        if row is None:
            return []
        ds = AnalysisDataset.model_validate_json(row["data"])
        preview = []
        for i in range(min(limit, ds.sample_count)):
            record = dict(ds.features[i]) if i < len(ds.features) else {}
            if i < len(ds.targets):
                record.update(ds.targets[i])
            preview.append(record)
        return preview
```

- [ ] **Step 3: Update excel.py to use DatasetRepository**

Replace the module-level `_store` and `_expiry` dicts. Inject `DatasetRepository`:

```python
# Remove: _store, _expiry, _purge_expired, save_dataset, get_dataset
# Add:
from process_opt.analysis.dataset_repo import DatasetRepository

_dataset_repo: DatasetRepository | None = None


def set_dataset_repo(repo: DatasetRepository) -> None:
    global _dataset_repo
    _dataset_repo = repo


def save_dataset(dataset: AnalysisDataset, ttl: int = 1800) -> str:
    if _dataset_repo is None:
        raise RuntimeError("DatasetRepository not initialized")
    return _dataset_repo.save(dataset, ttl=ttl)


def get_dataset(key: str) -> AnalysisDataset | None:
    if _dataset_repo is None:
        raise RuntimeError("DatasetRepository not initialized")
    return _dataset_repo.get(key)
```

- [ ] **Step 4: Wire up in main.py**

In `create_api_app_from_settings()`:
```python
from process_opt.analysis.excel import set_dataset_repo
from process_opt.analysis.dataset_repo import DatasetRepository

dataset_repo = DatasetRepository(pool)
set_dataset_repo(dataset_repo)

# Add background cleanup task
async def cleanup_datasets():
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        try:
            count = await dataset_repo.purge_expired()
            if count > 0:
                logger.info("Purged %d expired datasets", count)
        except Exception as e:
            logger.error("Dataset purge error: %s", e)

asyncio.create_task(cleanup_datasets())
```

- [ ] **Step 5: Verify build**

```bash
cd /Users/zhongding/dev/thingsboard && docker-compose down && docker-compose build backend-api 2>&1 | tail -3 && docker-compose up -d
sleep 25 && curl -s http://localhost:8000/health
```

- [ ] **Step 6: Commit**

```bash
git add db/init-db.sql src/process_opt/analysis/dataset_repo.py src/process_opt/analysis/excel.py src/process_opt/api/main.py
git commit -m "feat: PostgreSQL-backed dataset persistence replacing in-memory store"
```
