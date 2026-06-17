# Agent Framework Implementation Plan (P1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace OpenCode Docker container pool with LangGraph-based agent, JSON-driven process knowledge base, and 11 analysis tools for "点胶固化" process.

**Architecture:** LangGraph StateGraph with supervisor-worker pattern runs in-process alongside FastAPI. Knowledge base uses JSON templates. Existing analysis APIs remain unchanged, called directly via tool functions. Async + SSE streaming preserved from current architecture.

**Tech Stack:** langgraph, langchain-openai (DeepSeek via Volcengine ARK), FastAPI, Vue 3, existing scipy/sklearn analysis engine.

---

### Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add langgraph + langchain-openai + langchain-core**

```toml
dependencies = [
    ...
    "langgraph>=0.2.0",
    "langchain-openai>=0.2.0",
    "langchain-core>=0.3.0",
]
```

- [ ] **Step 2: Install dependencies**

```bash
pip install langgraph langchain-openai langchain-core
```

Alternatively rebuild Docker image:
```bash
docker-compose build backend-api && docker-compose up -d
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml && git commit -m "deps: add langgraph langchain-openai langchain-core"
```

---

### Task 2: Knowledge base models

**Files:**
- Create: `src/process_opt/knowledge/__init__.py`
- Create: `src/process_opt/knowledge/base.py`

- [ ] **Step 1: Create knowledge/__init__.py**

```python
from process_opt.knowledge.base import ProcessParameter, ProcessTemplate, QualityMetric, Rule
from process_opt.knowledge.loader import KnowledgeLoader

__all__ = ["ProcessTemplate", "ProcessParameter", "QualityMetric", "Rule", "KnowledgeLoader"]
```

- [ ] **Step 2: Create knowledge/base.py with pydantic models**

```python
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Importance(str, Enum):
    critical = "critical"
    important = "important"
    auxiliary = "auxiliary"


class ParamType(str, Enum):
    continuous = "continuous"
    discrete = "discrete"
    categorical = "categorical"


class ParameterRange(BaseModel):
    min: float
    max: float


class ProcessParameter(BaseModel):
    key: str
    name: str
    unit: str
    type: ParamType = ParamType.continuous
    range: ParameterRange
    target: ParameterRange
    importance: Importance = Importance.important
    description: str = ""
    notes: str = ""


class QualityMetric(BaseModel):
    key: str
    name: str
    unit: str
    description: str = ""
    usl: float | None = None
    lsl: float | None = None


class RuleType(str, Enum):
    hard_constraint = "hard_constraint"
    soft_guideline = "soft_guideline"
    dependency = "dependency"


class Rule(BaseModel):
    type: RuleType
    expression: str
    message: str
    trigger: str | None = None
    effect: str | None = None


class ProcessTemplate(BaseModel):
    process_type: str
    display_name: str
    description: str = ""
    parameters: list[ProcessParameter] = []
    quality_metrics: list[QualityMetric] = []
    rules: list[Rule] = []
    analysis_hints: list[str] = []
```

- [ ] **Step 3: Verify imports work**

```bash
cd src && python -c "from process_opt.knowledge.base import ProcessTemplate; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/knowledge/ && git commit -m "feat: knowledge base pydantic models"
```

---

### Task 3: Adhesive curing process template

**Files:**
- Create: `src/process_opt/knowledge/templates/adhesive_curing.json`

- [ ] **Step 1: Create the JSON template**

```json
{
  "process_type": "adhesive_curing",
  "display_name": "点胶固化",
  "description": "点胶固化工艺，包含点胶（dispensing）和固化（curing）两个步骤。点胶步骤控制胶量、压力；固化步骤控制温度和时间。最终质量由剪切强度、气泡率和胶水溢出量衡量。",
  "parameters": [
    {
      "key": "cure_temp",
      "name": "固化温度",
      "unit": "°C",
      "type": "continuous",
      "range": {"min": 80, "max": 180},
      "target": {"min": 120, "max": 150},
      "importance": "critical",
      "description": "固化温度直接影响胶水的交联反应速度。温度过低固化不完全，过高导致胶水老化。"
    },
    {
      "key": "cure_time",
      "name": "固化时间",
      "unit": "min",
      "type": "continuous",
      "range": {"min": 10, "max": 120},
      "target": {"min": 30, "max": 60},
      "importance": "critical",
      "description": "固化时间决定了交联反应的充分程度。时间过短固化不充分，过长浪费产能。"
    },
    {
      "key": "glue_amount",
      "name": "胶量",
      "unit": "mg",
      "type": "continuous",
      "range": {"min": 5, "max": 50},
      "target": {"min": 15, "max": 30},
      "importance": "critical",
      "description": "点胶量决定粘接强度。量少粘接不牢，量多溢出污染。"
    },
    {
      "key": "dispense_pressure",
      "name": "点胶压力",
      "unit": "kPa",
      "type": "continuous",
      "range": {"min": 50, "max": 300},
      "target": {"min": 100, "max": 200},
      "importance": "important",
      "description": "点胶压力影响胶水流速和点胶精度。压力过高导致溅射，过低导致断胶。"
    },
    {
      "key": "ambient_humidity",
      "name": "环境湿度",
      "unit": "%RH",
      "type": "continuous",
      "range": {"min": 20, "max": 80},
      "target": {"min": 30, "max": 60},
      "importance": "auxiliary",
      "description": "环境湿度影响胶水固化速度和粘接强度。过高湿度可能导致固化不良。"
    }
  ],
  "quality_metrics": [
    {
      "key": "shear_strength",
      "name": "剪切强度",
      "unit": "kgf/cm²",
      "usl": null,
      "lsl": 80.0,
      "description": "粘接面的抗剪切能力，越高越好"
    },
    {
      "key": "bubble_rate",
      "name": "气泡率",
      "unit": "%",
      "usl": 5.0,
      "lsl": null,
      "description": "固化后胶层内气泡占比，越低越好"
    },
    {
      "key": "glue_overflow",
      "name": "胶水溢出量",
      "unit": "mm",
      "usl": 1.0,
      "lsl": null,
      "description": "胶水从粘接面溢出的宽度，越小越好"
    }
  ],
  "rules": [
    {
      "type": "hard_constraint",
      "expression": "cure_temp > 180",
      "message": "固化温度不得超过180°C，否则会导致胶水老化和性能下降"
    },
    {
      "type": "hard_constraint",
      "expression": "cure_time < 10",
      "message": "固化时间不得少于10分钟，否则固化不完全"
    },
    {
      "type": "soft_guideline",
      "expression": "cure_temp > 150 and cure_time < 20",
      "message": "高温短时间可能导致固化不均匀，建议适当降低温度或延长时间"
    },
    {
      "type": "soft_guideline",
      "expression": "glue_amount > 40",
      "message": "胶量偏大可能导致溢出，建议控制在15-30mg"
    },
    {
      "type": "dependency",
      "trigger": "cure_temp increase",
      "effect": "可适当缩短 cure_time",
      "message": "固化温度每升高10°C，固化时间可减少约5分钟，但总时间不应低于15分钟"
    }
  ],
  "analysis_hints": [
    "优先分析固化温度、固化时间、胶量这三个关键参数与剪切强度的相关性",
    "如果气泡率高，检查固化温度和时间组合是否合理",
    "如果胶水溢出量大，检查胶量和点胶压力是否过高",
    "环境湿度超过60%时应关注其对固化质量的影响"
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/knowledge/templates/ && git commit -m "feat: adhesive curing process template"
```

---

### Task 4: Knowledge loader

**Files:**
- Create: `src/process_opt/knowledge/loader.py`

- [ ] **Step 1: Create loader.py**

```python
import json
import logging
from pathlib import Path
from typing import Any

from process_opt.knowledge.base import ProcessTemplate

logger = logging.getLogger(__name__)


class KnowledgeLoader:
    def __init__(self, templates_dir: Path | None = None) -> None:
        if templates_dir is None:
            templates_dir = Path(__file__).resolve().parent / "templates"
        self._dir = templates_dir
        self._cache: dict[str, ProcessTemplate] = {}

    def list_processes(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for fpath in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text())
                results.append({
                    "process_type": data["process_type"],
                    "display_name": data.get("display_name", data["process_type"]),
                })
            except Exception as e:
                logger.warning("Failed to read template %s: %s", fpath, e)
        return results

    def load(self, process_type: str) -> ProcessTemplate | None:
        if process_type in self._cache:
            return self._cache[process_type]

        fpath = self._dir / f"{process_type}.json"
        if not fpath.exists():
            logger.warning("Template not found: %s", fpath)
            return None

        try:
            data: dict[str, Any] = json.loads(fpath.read_text())
            template = ProcessTemplate(**data)
            self._cache[process_type] = template
            return template
        except Exception as e:
            logger.error("Failed to load template %s: %s", fpath, e)
            return None

    def build_system_prompt(self, template: ProcessTemplate) -> str:
        lines: list[str] = []
        lines.append(f"你是一个{template.display_name}工艺参数分析专家。")
        if template.description:
            lines.append(f"\n{template.description}\n")

        if template.parameters:
            lines.append("## 工艺参数\n")
            lines.append("| 参数 | 单位 | 允许范围 | 目标范围 | 等级 |")
            lines.append("|------|------|----------|----------|------|")
            for p in template.parameters:
                lines.append(
                    f"| {p.name}({p.key}) | {p.unit} | {p.range.min}-{p.range.max} | "
                    f"{p.target.min}-{p.target.max} | {p.importance.value} |"
                )

        if template.quality_metrics:
            lines.append("\n## 质量指标\n")
            for m in template.quality_metrics:
                spec = []
                if m.usl is not None:
                    spec.append(f"上限={m.usl}")
                if m.lsl is not None:
                    spec.append(f"下限={m.lsl}")
                spec_str = f" ({', '.join(spec)})" if spec else ""
                lines.append(f"- {m.name}({m.key}): {m.unit}{spec_str}")

        if template.rules:
            lines.append("\n## 工艺规则\n")
            for r in template.rules:
                prefix = "禁止:" if r.type == "hard_constraint" else "建议:"
                lines.append(f"- [{r.type.value}] {prefix} {r.message}")

        if template.analysis_hints:
            lines.append("\n## 分析建议\n")
            for h in template.analysis_hints:
                lines.append(f"- {h}")

        lines.append("\n## 输出要求\n")
        lines.append("- 使用中文回答，用 Markdown 格式（表格、列表）展示分析结果")
        lines.append("- 数据分析结果用表格呈现，不要输出原始 JSON")
        lines.append("- 在分析中引用工艺规则和约束条件")
        lines.append("- 给出可操作的参数调整建议")

        return "\n".join(lines)
```

- [ ] **Step 2: Test loader**

```bash
cd src && python -c "
from process_opt.knowledge.loader import KnowledgeLoader
loader = KnowledgeLoader()
# list
print('Processes:', loader.list_processes())
# load
t = loader.load('adhesive_curing')
print('Template:', t.display_name, 'params:', len(t.parameters))
# prompt
p = loader.build_system_prompt(t)
print('Prompt length:', len(p))
print(p[:200])
"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/knowledge/loader.py && git commit -m "feat: knowledge loader + system prompt builder"
```

---

### Task 5: Rule engine

**Files:**
- Create: `src/process_opt/knowledge/rules.py`

- [ ] **Step 1: Create rules.py**

```python
from process_opt.knowledge.base import ProcessTemplate, Rule, RuleType


class RuleCheck:
    def __init__(self, rule: Rule) -> None:
        self.rule = rule
        self.triggered = False
        self.violation = ""


class RuleEngine:
    def check_params(
        self, template: ProcessTemplate, params: dict[str, float]
    ) -> list[RuleCheck]:
        results: list[RuleCheck] = []
        for rule in template.rules:
            check = RuleCheck(rule)
            check.triggered = self._evaluate(rule.expression, params)
            if check.triggered:
                check.violation = rule.message
            results.append(check)
        return results

    def get_violations(
        self, checks: list[RuleCheck], severity: RuleType | None = None
    ) -> list[str]:
        messages: list[str] = []
        for c in checks:
            if not c.triggered:
                continue
            if severity and c.rule.type != severity:
                continue
            messages.append(c.rule.message)
        return messages

    @staticmethod
    def _evaluate(expression: str, params: dict[str, float]) -> bool:
        safe = {}
        for k, v in params.items():
            key = k.replace("-", "_").replace(" ", "_")
            safe[key] = v
        try:
            return bool(eval(expression, {"__builtins__": {}}, safe))
        except Exception:
            return False
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/knowledge/rules.py && git commit -m "feat: rule engine for process constraint checking"
```

---

### Task 6: Agent state

**Files:**
- Create: `src/process_opt/agent/__init__.py`
- Create: `src/process_opt/agent/state.py`

- [ ] **Step 1: Create agent/__init__.py**

```python
from process_opt.agent.graph import AgentSession, SessionManager, build_graph

__all__ = ["AgentSession", "SessionManager", "build_graph"]
```

- [ ] **Step 2: Create agent/state.py**

```python
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    process_type: str
    intent: str
    next: str
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/ && git commit -m "feat: agent state definition"
```

---

### Task 7: Prompt templates

**Files:**
- Create: `src/process_opt/agent/prompts/__init__.py`
- Create: `src/process_opt/agent/prompts/templates.py`

- [ ] **Step 1: Create prompts/__init__.py**

```python
from process_opt.agent.prompts.templates import build_chat_prompt, build_supervisor_prompt

__all__ = ["build_supervisor_prompt", "build_chat_prompt"]
```

- [ ] **Step 2: Create prompts/templates.py**

```python
SUPERVISOR_PROMPT = """你是一个路由节点，负责根据用户的意图将请求分发到合适的 Worker。

可用的 Worker:
- chat: 通用问答、工艺咨询、知识解答（不需要数据分析工具的请求）
- analyzer: 数据分析（分析数据、看相关性、SPC 监控、数据画像）
- recommender: 参数推荐和优化（优化参数、推荐参数组合、参数调整建议）
- FINISH: 对话可以结束或用户消息不需要进一步处理

根据用户最新消息和对话历史，只输出要路由到的 Worker 名称，不要输出其他内容。

Worker 名称: chat, analyzer, recommender, FINISH
"""


def build_supervisor_prompt(process_type: str) -> str:
    return SUPERVISOR_PROMPT


def build_chat_prompt(process_type: str, knowledge_prompt: str) -> str:
    return f"""你是工厂工艺参数分析助手，专注于{process_type}工艺。

{knowledge_prompt}

请根据用户的问题，结合工艺知识给出准确、可操作的建议。
如果需要查询数据，使用可用的工具。"""
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/prompts/ && git commit -m "feat: agent prompt templates"
```

---

### Task 8: Analysis tools

**Files:**
- Create: `src/process_opt/agent/tools/__init__.py`
- Create: `src/process_opt/agent/tools/analysis_tools.py`

- [ ] **Step 1: Create tools/__init__.py**

```python
from process_opt.agent.tools.analysis_tools import create_analysis_tools

__all__ = ["create_analysis_tools"]
```

- [ ] **Step 2: Create tools/analysis_tools.py**

```python
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from process_opt.analysis.schemas import (
    AnalysisDatasetRequest,
    CorrelationRequest,
    RecommendationRequest,
    RegressionRequest,
    SpcRequest,
)
from process_opt.knowledge.loader import KnowledgeLoader


def create_analysis_tools(
    repository: Any,
    analysis_service: Any,
    parameter_service: Any | None,
    knowledge_loader: KnowledgeLoader,
) -> list:
    @tool
    async def query_records(
        device_id: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """查询设备的生产数据记录。返回 barocdes, device_id, 参数值和检测结果。"""
        result = await repository.query_records(
            device_id=device_id or None, page=page, page_size=page_size,
        )
        return json.dumps(result, default=str, ensure_ascii=False)

    @tool
    async def get_devices() -> str:
        """获取系统中所有设备的 ID 列表。"""
        devices = await repository.list_devices()
        return json.dumps(devices, ensure_ascii=False)

    @tool
    async def get_stats() -> str:
        """获取平台统计数据（今日记录数、总记录数、设备数等）。"""
        stats = await repository.get_stats()
        return json.dumps(stats, default=str, ensure_ascii=False)

    @tool
    async def profile_data(device_id: str = "", page: int = 1, page_size: int = 50) -> str:
        """对设备数据进行统计画像（均值、标准差、最大最小值、异常值检测）。
        参数 device_id 为设备ID，page/page_size 控制查询记录数。"""
        req = AnalysisDatasetRequest(device_id=device_id, page=page, page_size=page_size)
        import json as _json
        results = await analysis_service.profile_from_request(req)
        items = [
            {
                "field": r.field,
                "count": r.count,
                "mean": round(r.mean, 3) if r.mean is not None else None,
                "std": round(r.std, 3) if r.std is not None else None,
                "min": round(r.min, 3) if r.min is not None else None,
                "max": round(r.max, 3) if r.max is not None else None,
                "outlier_count": r.outlier_count,
                "outlier_ratio": round(r.outlier_ratio, 3) if r.outlier_ratio else None,
            }
            for r in results
        ]
        return _json.dumps(items, ensure_ascii=False)

    @tool
    async def analyze_correlation(
        field_x: str, field_y: str, method: str = "pearson",
    ) -> str:
        """计算两个参数之间的相关性。field_x 和 field_y 是参数字段名，
        method 可选 'pearson' 或 'spearman'。返回相关系数和 p 值。"""
        req = CorrelationRequest(field_x=field_x, field_y=field_y, method=method)
        import json as _json
        result = await analysis_service.correlation(req)
        return _json.dumps({
            "field_x": result.field_x,
            "field_y": result.field_y,
            "coefficient": round(result.coefficient, 4),
            "p_value": round(result.p_value, 4),
            "method": result.method,
        }, ensure_ascii=False)

    @tool
    async def analyze_pareto(dataset_id: str, field_y: str) -> str:
        """对数据集进行帕累托分析，找出对 field_y 影响最大的因子排序。
        dataset_id 需先通过 build_dataset 获取。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.pareto import compute_pareto
        import json as _json
        ds = get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        items = compute_pareto(ds, field_y)
        return _json.dumps([i.model_dump() for i in items], ensure_ascii=False)

    @tool
    async def run_regression(
        dataset_id: str,
        feature_fields: list[str],
        target_field: str,
        model_type: str = "linear",
    ) -> str:
        """拟合回归模型，分析 feature_fields 对 target_field 的影响。
        model_type: 'linear'(线性回归) 或 'pls'(偏最小二乘)。返回 R²、RMSE、系数。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.regression import fit_regression
        import json as _json
        ds = get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        result = fit_regression(ds, feature_fields, target_field, model_type)
        return _json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def recommend_params(
        dataset_id: str,
        feature_fields: list[str],
        target_field: str,
        target_value: float,
    ) -> str:
        """根据历史数据和目标值，推荐最优参数组合。
        dataset_id 通过 build_dataset 获取。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.recommendation import compute_recommendation
        import json as _json
        ds = get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        req = RecommendationRequest(
            dataset_id=dataset_id,
            feature_fields=feature_fields,
            target_field=target_field,
            target_value=target_value,
        )
        result = compute_recommendation(ds, feature_fields, req)
        return _json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def run_spc(device_id: str, field: str = "") -> str:
        """对设备的工艺参数进行 SPC 监控分析，生成 I-MR 控制图数据、过程能力指数(Cp/Cpk)。
        参数 field 可选指定字段，为空则分析所有字段。"""
        req = SpcRequest(device_id=device_id, field=field or None)
        import json as _json
        result = await analysis_service.spc(req)
        return _json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def get_parameters(device_type: str = "") -> str:
        """获取参数集列表。device_type 可选按设备类型过滤。"""
        if parameter_service is None:
            from process_opt.parameters.schemas import ParameterSet
            return "Parameter service not available"
        import json as _json
        sets = await parameter_service.list_sets()
        return _json.dumps([s.model_dump() for s in sets], default=str, ensure_ascii=False)

    @tool
    async def get_process_knowledge(process_type: str) -> str:
        """获取指定工艺的参数模板、质量指标、规则约束和分析建议。
        process_type 例如 'adhesive_curing'。"""
        template = knowledge_loader.load(process_type)
        if template is None:
            return f"未找到工艺 '{process_type}' 的知识模板"
        return knowledge_loader.build_system_prompt(template)

    @tool
    async def build_dataset(device_id: str, since: str = "") -> str:
        """从数据库查询设备数据并构建分析数据集。
        device_id: 设备ID。since: ISO 8601 起始时间（可选）。
        返回 dataset_id 供其他分析工具使用。"""
        from process_opt.analysis.excel import get_dataset
        import json as _json

        since_dt: datetime | None = None
        if since:
            since_dt = datetime.fromisoformat(since)

        ds_id = await analysis_service._builder.build_to_dataset_id(
            device_id, since=since_dt,
        )
        ds = get_dataset(ds_id)
        feature_fields = sorted({k for f in ds.features for k in f}) if ds else []
        target_fields = sorted({k for t in ds.targets for k in t}) if ds else []
        return _json.dumps({
            "dataset_id": ds_id,
            "fields": {"features": feature_fields, "targets": target_fields},
            "sample_count": ds.sample_count if ds else 0,
        }, ensure_ascii=False)

    return [
        query_records,
        get_devices,
        get_stats,
        profile_data,
        analyze_correlation,
        analyze_pareto,
        run_regression,
        recommend_params,
        run_spc,
        get_parameters,
        get_process_knowledge,
        build_dataset,
    ]
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/ && git commit -m "feat: 12 analysis tools wrapping existing APIs"
```

---

### Task 9: Supervisor node

**Files:**
- Create: `src/process_opt/agent/nodes/__init__.py`
- Create: `src/process_opt/agent/nodes/supervisor.py`

- [ ] **Step 1: Create nodes/__init__.py**

```python
# empty
```

- [ ] **Step 2: Create nodes/supervisor.py**

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from process_opt.agent.state import AgentState

WORKERS = ["chat", "analyzer", "recommender"]


def create_supervisor_node(llm: BaseChatModel):
    async def supervisor_node(state: AgentState) -> dict:
        messages = [
            SystemMessage(
                content=(
                    "你是一个路由节点，负责根据用户的意图将请求分发到合适的 Worker。\n\n"
                    "可用的 Worker:\n"
                    "- chat: 通用问答、工艺咨询、知识解答\n"
                    "- analyzer: 数据分析（看相关性、SPC监控、数据画像）\n"
                    "- recommender: 参数推荐和优化\n"
                    "- FINISH: 对话结束\n\n"
                    "只输出 Worker 名称，不要其他内容。\n"
                    "Worker: chat, analyzer, recommender, FINISH"
                )
            ),
        ]

        last_msg = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_msg = msg
                break
        if last_msg:
            messages.append(last_msg)

        response = await llm.ainvoke(messages)
        text = (response.content or "").strip()

        for worker in WORKERS:
            if worker in text:
                return {"next": worker}
        return {"next": "FINISH"}

    return supervisor_node
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/nodes/ && git commit -m "feat: supervisor routing node"
```

---

### Task 10: Chat node

**Files:**
- Create: `src/process_opt/agent/nodes/chat.py`

- [ ] **Step 1: Create nodes/chat.py**

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


def create_chat_node(llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    async def chat_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""

        system_message = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}工艺参数分析助手。\n\n"
                f"{knowledge_prompt}\n\n"
                "用中文回答，使用 Markdown 格式。"
                "数据分析结果用表格呈现，不要输出原始 JSON。"
            )
        )

        messages = [system_message] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return chat_node
```

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/agent/nodes/chat.py && git commit -m "feat: chat worker node"
```

---

### Task 11: Analyzer + Recommender nodes

**Files:**
- Create: `src/process_opt/agent/nodes/analyzer.py`
- Create: `src/process_opt/agent/nodes/recommender.py`

- [ ] **Step 1: Create nodes/analyzer.py**

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


def create_analyzer_node(llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    async def analyzer_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""

        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}工艺数据分析专家。\n\n"
                f"{knowledge_prompt}\n\n"
                "你的任务：\n"
                "1. 根据用户需求选择合适的分析工具（相关性、回归、SPC、画像等）\n"
                "2. 调用工具获取分析结果\n"
                "3. 用中文解读结果，结合工艺规则给出分析结论\n"
                "4. 使用表格和图表（mermaid/echarts）呈现数据\n"
                "5. 不要输出原始 JSON"
            )
        )

        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return analyzer_node
```

- [ ] **Step 2: Create nodes/recommender.py**

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from process_opt.agent.state import AgentState
from process_opt.knowledge.loader import KnowledgeLoader


def create_recommender_node(llm: BaseChatModel, knowledge_loader: KnowledgeLoader):
    async def recommender_node(state: AgentState) -> dict:
        process_type = state.get("process_type", "adhesive_curing")
        template = knowledge_loader.load(process_type)
        knowledge_prompt = knowledge_loader.build_system_prompt(template) if template else ""

        system = SystemMessage(
            content=(
                f"你是{template.display_name if template else process_type}工艺参数推荐专家。\n\n"
                f"{knowledge_prompt}\n\n"
                "你的任务：\n"
                "1. 使用 build_dataset 构建数据集\n"
                "2. 使用 run_regression 分析参数与质量的关系\n"
                "3. 使用 recommend_params 获取最优参数建议\n"
                "4. 结合工艺规则过滤不合理的推荐\n"
                "5. 输出来源和置信度说明\n"
                "6. 给出参数调整梯度建议\n"
                "7. 使用表格呈现推荐参数\n"
                "8. 不要输出原始 JSON"
            )
        )

        messages = [system] + list(state["messages"])
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    return recommender_node
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/nodes/analyzer.py src/process_opt/agent/nodes/recommender.py
git commit -m "feat: analyzer and recommender worker nodes"
```

---

### Task 12: Graph builder + Session manager

**Files:**
- Create: `src/process_opt/agent/graph.py`

- [ ] **Step 1: Create graph.py with build_graph, AgentSession, SessionManager**

```python
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from process_opt.agent.nodes.analyzer import create_analyzer_node
from process_opt.agent.nodes.chat import create_chat_node
from process_opt.agent.nodes.recommender import create_recommender_node
from process_opt.agent.nodes.supervisor import create_supervisor_node
from process_opt.agent.state import AgentState
from process_opt.agent.tools.analysis_tools import create_analysis_tools
from process_opt.knowledge.loader import KnowledgeLoader

logger = logging.getLogger(__name__)

WORKERS = ["chat", "analyzer", "recommender"]


def build_graph(
    llm: Any,
    llm_with_tools: Any,
    tools: list,
    knowledge_loader: KnowledgeLoader,
):
    supervisor_node = create_supervisor_node(llm)
    chat_node = create_chat_node(llm_with_tools, knowledge_loader)
    analyzer_node = create_analyzer_node(llm_with_tools, knowledge_loader)
    recommender_node = create_recommender_node(llm_with_tools, knowledge_loader)

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("recommender", recommender_node)
    workflow.add_node("tools", ToolNode(tools))

    workflow.set_entry_point("supervisor")

    for worker in WORKERS:
        workflow.add_edge(worker, "supervisor")
    workflow.add_edge("tools", "supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state.get("next", "FINISH"),
        {
            **{w: w for w in WORKERS},
            **{"tools": "tools"},
            "FINISH": END,
        },
    )

    return workflow.compile()


class AgentSession:
    def __init__(
        self,
        session_id: str,
        user_id: str,
        process_type: str,
        graph: Any,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.process_type = process_type
        self.graph = graph
        self.config = {"configurable": {"thread_id": session_id}}
        self.state: dict = {
            "messages": [],
            "user_id": user_id,
            "process_type": process_type,
            "intent": "",
            "next": "supervisor",
        }
        self.event_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._running = False
        self.last_active = time.monotonic()

    async def send_message(self, text: str) -> None:
        from langchain_core.messages import HumanMessage

        self.state["messages"].append(HumanMessage(content=text))
        self.state["next"] = "supervisor"
        self._running = True
        asyncio.create_task(self._run_graph())

    async def _run_graph(self) -> None:
        try:
            async for event in self.graph.astream_events(
                self.state, self.config, version="v2",
            ):
                await self.event_queue.put(event)
        except Exception as e:
            logger.error("Graph execution error for session %s: %s", self.session_id, e)
            await self.event_queue.put({"type": "error", "message": str(e)})
        finally:
            self._running = False
            await self.event_queue.put({"type": "done"})
            self.last_active = time.monotonic()

    def get_messages(self) -> list[dict]:
        from langchain_core.messages import BaseMessage

        result: list[dict] = []
        for msg in self.state.get("messages", []):
            if isinstance(msg, BaseMessage):
                result.append({
                    "role": getattr(msg, "type", "unknown"),
                    "content": msg.content if hasattr(msg, "content") else str(msg),
                })
        return result


class SessionManager:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def create(
        self,
        user_id: str,
        process_type: str,
        graph: Any,
    ) -> AgentSession:
        sid = f"ses_{uuid.uuid4().hex[:20]}"
        session = AgentSession(sid, user_id, process_type, graph)
        async with self._lock:
            self._sessions[sid] = session
        return session

    async def get(self, session_id: str) -> AgentSession | None:
        session = self._sessions.get(session_id)
        if session:
            session.last_active = time.monotonic()
        return session

    async def list_user(self, user_id: str) -> list[dict]:
        results: list[dict] = []
        for s in self._sessions.values():
            if s.user_id == user_id:
                results.append({
                    "session_id": s.session_id,
                    "process_type": s.process_type,
                    "message_count": len(s.state.get("messages", [])),
                })
        return results

    async def expire_stale(self) -> None:
        now = time.monotonic()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
            logger.info("Expired session %s", sid)
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/agent/graph.py && git commit -m "feat: graph builder, session manager, AgentSession"
```

---

### Task 13: API routes + SSE

**Files:**
- Create: `src/process_opt/api/agent_routes.py`

- [ ] **Step 1: Create agent_routes.py**

```python
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from langchain_core.messages import AIMessageChunk
from starlette.responses import StreamingResponse

from process_opt.agent.graph import SessionManager
from process_opt.knowledge.loader import KnowledgeLoader

logger = logging.getLogger(__name__)


def register_agent_routes(
    app: Any,
    session_manager: SessionManager,
    knowledge_loader: KnowledgeLoader,
    graph: Any,
) -> None:
    router = APIRouter(prefix="/api/v1/agent")

    @router.post("/session")
    async def create_session(request: Request) -> dict:
        user = request.headers.get("X-User", "anonymous")
        body = await request.json()
        process_type = body.get("process_type", "adhesive_curing")
        session = await session_manager.create(user, process_type, graph)
        return {
            "session_id": session.session_id,
            "process_type": process_type,
        }

    @router.get("/session")
    async def list_sessions(request: Request) -> list[dict]:
        user = request.headers.get("X-User", "anonymous")
        return await session_manager.list_user(user)

    @router.post("/chat")
    async def send_message(request: Request) -> Response:
        body = await request.json()
        session_id = body.get("session_id", "")
        text = body.get("text", "")
        if not session_id or not text:
            raise HTTPException(status_code=400, detail="session_id and text required")

        session = await session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话已过期，请重新开始")

        await session.send_message(text)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/chat/{session_id}/events")
    async def stream_events(session_id: str) -> StreamingResponse:
        session = await session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        async def generate():
            try:
                while True:
                    event = await session.event_queue.get()
                    if event.get("type") == "done":
                        yield b'data: {"type":"session.status","status":"idle"}\n\n'
                        break
                    if event.get("type") == "error":
                        err = json.dumps({"type":"error","message":event["message"]})
                        yield f"data: {err}\n\n".encode()
                        yield b'data: {"type":"session.status","status":"idle"}\n\n'
                        break

                    sse = _map_event(event)
                    if sse:
                        yield sse
            except Exception as e:
                logger.error("SSE stream error: %s", e)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/session/{session_id}/messages")
    async def get_messages(session_id: str) -> list[dict]:
        session = await session_manager.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.get_messages()

    # Knowledge endpoints
    @router.get("/processes")
    async def list_processes() -> list[dict]:
        return knowledge_loader.list_processes()

    app.include_router(router)


def _map_event(event: dict) -> bytes | None:
    kind = event.get("event", "")

    if kind == "on_chat_model_stream":
        chunk: Any = event.get("data", {}).get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            text = chunk.content
            if isinstance(text, list):
                text = "".join(str(t) for t in text)
            data = json.dumps({"type": "message.delta", "text": str(text)})
            return f"data: {data}\n\n".encode()
        return None

    if kind == "on_tool_start":
        name = event.get("name", "")
        inp = event.get("data", {}).get("input", {})
        args = {k: v for k, v in inp.items() if not k.startswith("_")}
        data = json.dumps({"type": "tool.call", "name": name, "args": args}, default=str)
        return f"data: {data}\n\n".encode()

    if kind == "on_tool_end":
        name = event.get("name", "")
        output = event.get("data", {}).get("output", "")
        data = json.dumps({"type": "tool.result", "name": name, "data": str(output)})
        return f"data: {data}\n\n".encode()

    if kind == "on_chain_start":
        node_name = event.get("name", "")
        if node_name in ("chat", "analyzer", "recommender"):
            data = json.dumps({"type": "node.start", "node": node_name})
            return f"data: {data}\n\n".encode()

    if kind == "on_chain_end":
        node_name = event.get("name", "")
        if node_name in ("chat", "analyzer", "recommender"):
            data = json.dumps({"type": "node.end", "node": node_name})
            return f"data: {data}\n\n".encode()

    return None
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/api/agent_routes.py && git commit -m "feat: agent API routes + SSE streaming"
```

---

### Task 14: Settings + LLM factory

**Files:**
- Modify: `src/process_opt/common/settings.py`

- [ ] **Step 1: Add DeepSeek/Agent settings**

Append before the closing of the Settings class:

```python
    # Agent settings
    agent_model: str = "ark-code-latest"
    agent_api_base: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    agent_api_key: str = ""  # set via PROCESS_OPT_AGENT_API_KEY env var
    agent_temperature: float = 0.0
    agent_session_ttl: int = 1800
```

- [ ] **Step 2: Commit**

```bash
git add src/process_opt/common/settings.py && git commit -m "feat: agent settings (model, API key, TTL)"
```

---

### Task 15: Wire into app.py and main.py

**Files:**
- Modify: `src/process_opt/api/app.py`
- Modify: `src/process_opt/api/main.py`

- [ ] **Step 1: In app.py, add agent parameter to create_app signature**

```python
def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisService | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
    container_pool: "ContainerPoolProxy | None" = None,
    agent_graph: Any = None,          # ← NEW
    session_manager: Any = None,      # ← NEW
    knowledge_loader: Any = None,     # ← NEW
) -> FastAPI:
```

Then after the `if container_pool is not None:` block (around line 581), add:

```python
    if agent_graph is not None and session_manager is not None and knowledge_loader is not None:
        from process_opt.api.agent_routes import register_agent_routes
        register_agent_routes(app, session_manager, knowledge_loader, agent_graph)
```

- [ ] **Step 2: In main.py, initialize agent components in lifespan**

After `analysis_service = AnalysisService(dataset_builder)` line, add:

```python
        # Initialize LangGraph agent
        from process_opt.agent.graph import build_graph, SessionManager
        from process_opt.agent.tools.analysis_tools import create_analysis_tools
        from process_opt.knowledge.loader import KnowledgeLoader
        from langchain_openai import ChatOpenAI

        knowledge_loader = KnowledgeLoader()
        tools = create_analysis_tools(
            repository_proxy, analysis_service_proxy, parameter_service_proxy, knowledge_loader,
        )

        llm = ChatOpenAI(
            model=settings.agent_model,
            base_url=settings.agent_api_base,
            api_key=settings.agent_api_key,
            temperature=settings.agent_temperature,
            streaming=True,
        )
        llm_with_tools = llm.bind_tools(tools)
        agent_graph = build_graph(llm, llm_with_tools, tools, knowledge_loader)
        session_manager = SessionManager(ttl_seconds=settings.agent_session_ttl)
```

In the create_app call (now needs to pass agent parameters):

```python
    app = create_app(
        repository=repository_proxy,
        parameter_service=parameter_service_proxy,
        analysis_service=analysis_service_proxy,
        line_device_repo=line_device_repo_proxy,
        container_pool=container_pool_proxy,
        agent_graph=agent_graph,           # ← NEW
        session_manager=session_manager,   # ← NEW
        knowledge_loader=knowledge_loader, # ← NEW
    )
```

In the lifespan cleanup (finally block), add:

```python
            import gc
            gc.collect()  # release LangGraph objects
```

- [ ] **Step 3: Rebuild and test backend startup**

```bash
docker-compose build backend-api && docker-compose up -d
sleep 30
curl -s http://localhost:8000/health
```

- [ ] **Step 4: Test create session + chat + SSE**

```bash
# Create session
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/agent/session \
  -H "X-User: test" -H "Content-Type: application/json" \
  -d '{"process_type":"adhesive_curing"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "Session: $SESSION"

# Send message (async)
curl -s -o /dev/null -w "HTTP %{http_code} (%{time_total}s)\n" \
  -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "X-User: test" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\",\"text\":\"分析固化温度对剪切强度的影响\"}"

# Stream SSE
curl -s --max-time 15 "http://localhost:8000/api/v1/agent/chat/$SESSION/events"
```

- [ ] **Step 5: Commit**

```bash
git add src/process_opt/api/app.py src/process_opt/api/main.py
git commit -m "feat: wire agent into FastAPI app"
```

---

### Task 16: Frontend agent API client

**Files:**
- Create: `web/src/api/agent.ts`

- [ ] **Step 1: Create agent.ts (mirroring opencode.ts pattern)**

```typescript
import { useSessionStore } from '@/stores/session'

const ENGINE = import.meta.env.VITE_AGENT_ENGINE || 'langgraph'
const API_URL = import.meta.env.DEV
  ? (ENGINE === 'opencode' ? '/opencode' : '/api/v1/agent')
  : (ENGINE === 'opencode' ? 'http://localhost:8000/api/opencode' : 'http://localhost:8000/api/v1/agent')

function getCurrentUser(): string {
  const store = useSessionStore()
  return store.currentUser || 'anonymous'
}

interface AgentSession {
  session_id?: string
  id?: string
  process_type?: string
  title?: string
}

interface ChatMessage {
  role: string
  content: string
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...opts,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-User': getCurrentUser(),
        ...opts?.headers,
      },
    })
    if (!res.ok) {
      const body = await res.text()
      let detail = `${res.status} ${res.statusText}`
      try { detail = JSON.parse(body).detail || detail } catch {}
      throw new Error(detail)
    }
    return res.json() as Promise<T>
  } finally {
    clearTimeout(timeout)
  }
}

export async function listSessions(): Promise<AgentSession[]> {
  const sessions = await request<any[]>('/session')
  return sessions.map((s: any) => ({
    id: s.session_id || s.id,
    title: s.process_type || s.title || '',
    process_type: s.process_type,
  }))
}

export async function createSession(processType?: string): Promise<AgentSession> {
  const res = await request<any>('/session', {
    method: 'POST',
    body: JSON.stringify({ process_type: processType || 'adhesive_curing' }),
  })
  return { id: res.session_id || res.id, process_type: res.process_type }
}

export async function sendMessageAsync(sessionId: string, text: string): Promise<void> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)
  try {
    const res = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-User': getCurrentUser(),
      },
      body: JSON.stringify({ session_id: sessionId, text }),
    })
    if (!res.ok) {
      const body = await res.text()
      let detail = `${res.status} ${res.statusText}`
      try { detail = JSON.parse(body).detail || detail } catch {}
      throw new Error(detail)
    }
  } finally {
    clearTimeout(timeout)
  }
}

export interface StreamEvents {
  cancel: () => void
  promise: Promise<void>
}

export function streamEvents(
  sessionId: string,
  onDelta: (delta: string) => void,
  onToolCall: (name: string, args: any) => void,
  onToolResult: (name: string, data: string) => void,
  onNodeStart: (node: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): StreamEvents {
  const controller = new AbortController()

  const promise = (async () => {
    try {
      const res = await fetch(`${API_URL}/chat/${encodeURIComponent(sessionId)}/events`, {
        signal: controller.signal,
        headers: { 'X-User': getCurrentUser() },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!res.body) throw new Error('No response body')

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
            switch (event.type) {
              case 'message.delta':
                onDelta(event.text || '')
                break
              case 'tool.call':
                onToolCall(event.name, event.args)
                break
              case 'tool.result':
                onToolResult(event.name, event.data)
                break
              case 'node.start':
                onNodeStart(event.node)
                break
              case 'session.status':
                if (event.status === 'idle') {
                  onDone()
                  return
                }
                break
              case 'error':
                onError(event.message || '')
                return
            }
          } catch {}
        }
      }
      onDone()
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        onError(e.message || '流中断')
      }
    }
  })()

  return { cancel: () => controller.abort(), promise }
}

export async function getMessages(sessionId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/session/${encodeURIComponent(sessionId)}/messages`)
}

export async function listProcesses(): Promise<{process_type: string; display_name: string}[]> {
  const PROC_API = import.meta.env.DEV ? '/api/v1/agent' : 'http://localhost:8000/api/v1/agent'
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const res = await fetch(`${PROC_API}/processes`, {
      signal: controller.signal,
      headers: { 'X-User': getCurrentUser() },
    })
    if (!res.ok) return [{ process_type: 'adhesive_curing', display_name: '点胶固化' }]
    return res.json()
  } catch {
    return [{ process_type: 'adhesive_curing', display_name: '点胶固化' }]
  } finally {
    clearTimeout(timeout)
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/agent.ts && git commit -m "feat: frontend agent API client (LangGraph + OpenCode dual)"
```

---

### Task 17: Adapt AgentChat.vue

**Files:**
- Modify: `web/src/components/AgentChat.vue`

The key change is in the `<script setup>` imports and the `send()` function. Replace imports and use agent.ts instead of opencode.ts.

- [ ] **Step 1: Replace imports at top of script**

```typescript
import { listSessions, createSession, sendMessageAsync, streamEvents, getMessages, listProcesses, type StreamEvents } from '@/api/agent'
```

Remove the opencode import.

- [ ] **Step 2: Add process_type selection**

Add these reactive variables:

```typescript
const processTypes = ref<{process_type: string; display_name: string}[]>([])
const currentProcessType = ref('adhesive_curing')

onMounted(async () => {
  processTypes.value = await listProcesses()
  ...
})
```

- [ ] **Step 3: In createNewSession, pass process_type**

```typescript
async function createNewSession() {
  try {
    const res = await createSession(currentProcessType.value)
    ...
  }
}
```

- [ ] **Step 4: Replace send() function**

```typescript
async function send() {
  const text = input.value.trim(); if (!text || loading.value) return
  input.value = ''; error.value = ''
  messages.value.push({ role: 'user', text, parts: [{ type: 'text', text }] })
  loading.value = true; scrollBottom()
  try {
    if (!sessionId.value) { await createNewSession(); sessionStorage.setItem('opencode-session', sessionId.value) }

    const assistantIdx = messages.value.length
    messages.value.push({ role: 'assistant', text: '', parts: [{ type: 'text', text: '' }] })
    scrollBottom()

    const sid = sessionId.value
    await sendMessageAsync(sid, text)

    activeStream = streamEvents(
      sid,
      (delta: string) => {
        const parts = messages.value[assistantIdx]?.parts
        if (parts && parts.length > 0) {
          const last = parts[parts.length - 1]
          if (last.type === 'text') {
            last.text = (last.text || '') + delta
          }
        }
        scrollBottom()
      },
      (name: string, args: any) => {
        messages.value[assistantIdx]?.parts.push({
          type: 'tool_call', text: '', tool: name, args: JSON.stringify(args),
        })
        scrollBottom()
      },
      (name: string, data: string) => {
        messages.value[assistantIdx]?.parts.push({
          type: 'tool_result', text: data.slice(0, 500), tool: name,
        })
        scrollBottom()
      },
      (node: string) => {},
      () => {
        loading.value = false
        activeStream = null
        scrollBottom()
      },
      (err: string) => {
        error.value = err
        loading.value = false
        activeStream = null
        scrollBottom()
      },
    )
  } catch (e: any) {
    error.value = '请求失败: ' + (e.message || '')
    loading.value = false
    activeStream = null
    scrollBottom()
  }
}
```

- [ ] **Step 5: Add process selector to template header**

After `showSessions` toggle button, add:

```html
<el-dropdown trigger="click" @command="(v: string) => { currentProcessType = v; newSession() }">
  <el-button text size="small">{{ processTypes.find(p => p.process_type === currentProcessType)?.display_name || '胶固' }}</el-button>
  <template #dropdown>
    <el-dropdown-menu>
      <el-dropdown-item v-for="p in processTypes" :key="p.process_type" :command="p.process_type">
        {{ p.display_name }}
      </el-dropdown-item>
    </el-dropdown-menu>
  </template>
</el-dropdown>
```

- [ ] **Step 6: Build frontend and test**

```bash
cd web && npx vite build
```

- [ ] **Step 7: Commit**

```bash
git add web/src/components/AgentChat.vue web/src/api/agent.ts
git commit -m "feat: adapt AgentChat to LangGraph agent + process selector"
```

---

### Task 18: Vite proxy for new agent routes

**Files:**
- Modify: `web/vite.config.ts`

- [ ] **Step 1: Add agent proxy rule**

Add alongside the existing `/opencode` proxy:

```typescript
'/api/v1/agent': {
  target: 'http://localhost:8000',
  changeOrigin: true,
},
```

- [ ] **Step 2: Commit**

```bash
git add web/vite.config.ts && git commit -m "feat: vite proxy for /api/v1/agent"
```

---

### Task 19: End-to-end verification

- [ ] **Step 1: Full system restart**

```bash
docker-compose down --remove-orphans
docker-compose build backend-api
docker-compose up -d
sleep 35
```

- [ ] **Step 2: Verify health**

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/v1/agent/processes
```

- [ ] **Step 3: E2E chat test**

```bash
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/agent/session \
  -H "X-User: test" -H "Content-Type: application/json" \
  -d '{"process_type":"adhesive_curing"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

curl -s -o /dev/null -w "Chat: HTTP %{http_code} (%{time_total}s)\n" \
  -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "X-User: test" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\",\"text\":\"固化温度对强度有什么影响？\"}"

curl -s --max-time 30 "http://localhost:8000/api/v1/agent/chat/$SESSION/events"
```

- [ ] **Step 4: Commit any fixes**

---

## Self-Review

**Spec coverage check:**
- [x] Knowledge base (knowledge/ package) → Tasks 2-5
- [x] Agent skeleton (agent/ package) → Tasks 6, 12
- [x] Supervisor-Worker graph → Tasks 9-12
- [x] Tool definitions (11+ tools) → Task 8
- [x] API routes + SSE → Task 13
- [x] Frontend adaptation → Tasks 16-18
- [x] Settings → Task 14
- [x] Integration → Task 15
- [x] Migration (dual-engine) → Task 16 (VITE_AGENT_ENGINE)
- [x] Cleanup → Not in P1 (pending P2+)

**Placeholder scan:** No TBD, TODO, or vague requirements. All code steps have concrete content.

**Type consistency:** AgentState fields match across state.py, nodes, and graph.py. SSE event names match agent_routes.py and agent.ts.

**Score: 0 gaps, 0 placeholders**
