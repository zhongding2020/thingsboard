# Agent 系统优化设计

**日期**: 2026-06-18  
**基于**: 工艺智能体系统全面审计结果

## 优化项概览

| # | 优化项 | 影响范围 | 复杂度 |
|---|---|---|---|
| 1 | RuleEngine 接入 recommend 工具 | 1 文件 | 低 |
| 2 | Worker 节点工厂化重构 | 3→1 文件 | 中 |
| 3 | ANOVA 使用实际设计矩阵 | 2 文件 | 中 |
| 4 | _extract_arrays 提取共享 | 6 文件 | 低 |
| 5 | Supervisor 结构化输出 | 1 文件 | 低 |
| 6 | Latin Hypercube 推荐采样 | 1 文件 | 中 |
| 7 | DOE replicates + 数据集持久化 | 3 文件 | 高 |
| 8 | 工具输出全改 Markdown | 8 文件 | 中 |
| 9 | 错误处理增强 | 2 文件 | 低 |

---

## 1. RuleEngine 接入 recommend 工具

**问题**: `knowledge/rules.py` 中 `RuleEngine` 完整实现但从未调用，推荐结果不校验规则。

**方案**:
- 在 `recommend_params` 工具中，生成候选参数后调用 `RuleEngine.check_params(template, candidates)` 对每个候选点做校验
- 在工具返回中追加违规信息，如 "⚠ 候选 #3: 固化温度 205°C 超过上限 200°C"
- 候选排序优先级：合规 > 少量 warning > 违规
- `analysis_tools.py` 中约第 230 行插入

**文件**: `src/process_opt/agent/tools/analysis_tools.py`

---

## 2. Worker 节点工厂化

**问题**: `chat.py` / `analyzer.py` / `recommender.py` 90% 重复代码。

**方案**:
- 创建 `agent/nodes/worker.py`，导出 `create_worker_node(role: str, tools: list)` 工厂函数
- `role` 参数: `"chat"` | `"analyzer"` | `"recommender"`
- 工厂内部根据 role 切换 system prompt 角色描述
- 三个旧文件删除，`graph.py` 改用 `create_worker_node(role, llm, tools)`

**文件**:
- 创建: `src/process_opt/agent/nodes/worker.py`
- 修改: `src/process_opt/agent/graph.py` (引用新工厂)
- 删除: `agent/nodes/chat.py`, `agent/nodes/analyzer.py`, `agent/nodes/recommender.py`

---

## 3. ANOVA 使用实际设计矩阵

**问题**: `analyze_experiment` 工具在 ANOVA 时硬编码全因子生成，非全因子实验得错误 p 值。

**方案**:
- 修改 `doe_service.py` 的 `run_anova()` 函数签名，接受 `design_matrix: list[list[float]]` 参数
- `analyze_experiment` 工具改为传递 `design_runs` 的实际矩阵而非重新生成
- 工具已存储 `plan.design_runs`，直接提取因子水平列即可

**文件**:
- `src/process_opt/analysis/doe_service.py`
- `src/process_opt/agent/tools/analysis_tools.py` (analyze_experiment 工具)

---

## 4. _extract_arrays 提取共享

**问题**: 同一函数在 5 个文件中重复定义。

**方案**:
- 创建 `src/process_opt/analysis/utils.py`
- 移入 `_extract_arrays(dataset, feature_fields, target_field)` 和辅助函数
- correlation.py, regression.py, recommendation.py, importance.py, optimization.py 改为 `from .utils import extract_arrays`

**文件**: 创建 1 + 修改 5

---

## 5. Supervisor 结构化输出

**问题**: LLM 文本输出 + 字符串匹配 (`"analyzer" in text`) 不可靠。

**方案**:
```python
from pydantic import BaseModel, Field
from typing import Literal

class SupervisorDecision(BaseModel):
    intent: Literal["CHAT", "ANALYZER", "RECOMMENDER", "FINISH"]

structured_llm = llm.with_structured_output(SupervisorDecision, method="function_calling")
result = structured_llm.invoke(prompt)
```

**文件**: `src/process_opt/agent/nodes/supervisor.py`

---

## 6. Latin Hypercube 推荐采样

**问题**: 5 因素 × 10 步 = 100k 组合超 10k 上限，全网格不可行。

**方案**:
- 在 `recommendation.py` 中，当 `_generate_grid` 检测组合数 > `MAX_GRID_COMBINATIONS` 时，切换为 Latin Hypercube Sampling
- 采样 5000 个均匀分布的点（`pyDOE2` 不支持 LHS，需自行实现或引入 `scipy.stats.qmc.LatinHypercube`）
- 使用 `scipy.stats.qmc.LatinHypercube(d=len(factors)).random(n=5000)` 生成采样点
- 采样点映射回各因素的实际范围，代入模型预测，排序取 Top N

**文件**: `src/process_opt/analysis/recommendation.py`

---

## 7. DOE replicates + 数据集持久化

### 7a. DOE replicates
**问题**: `DOEConfig.replicates` 字段存在但从未生效。

**方案**: 在 `doe_service.generate_design()` 中，生成基础设计矩阵后，按 `replicates` 值重复追加行。

### 7b. 数据集持久化
**问题**: Excel 上传和 DB 查询构建的数据集存在内存 dict 中，重启丢失。

**方案**:
- 新建表 `datasets(id UUID PK, name text, data JSONB, created_at timestamp, expires_at timestamp)`
- `dataset.py` 改为写入 PostgreSQL 而非内存 dict
- 查询时检查 `expires_at > now()`
- 服务启动时增加 TTL 清理任务
- Excel 解析保持 openpyxl，解析后的 `AnalysisDataset` 序列化为 JSONB

**文件**:
- 修改: `db/init-db.sql` (新表)
- 创建: `src/process_opt/analysis/dataset_repo.py` (PostgreSQL CRUD)
- 修改: `src/process_opt/analysis/excel.py` (save_dataset → PostgreSQL)
- 修改: `src/process_opt/analysis/doe_service.py` (replicates)

---

## 8. 工具输出全改 Markdown

**问题**: 所有工具返回 `json.dumps(...)` 字符串，LLM 需自行解析。

**方案**: 改为返回 Markdown 字符串，关键工具:

| 工具 | 输出格式 |
|---|---|
| `profile_data` | Markdown 表格 (mean/std/min/max/outliers) |
| `analyze_correlation` | Markdown 表格 + ECharts 热力图 JSON |
| `run_regression` | Markdown (R², RMSE, 系数表, 残差 ECharts) |
| `analyze_pareto` | Markdown 表格 + ECharts 帕累托图 |
| `recommend_params` | Markdown 表格 (Top 10 候选 + 预测值 + 合规状态) |
| `run_spc` | Markdown (Cp, Cpk, 控制界限) + ECharts 图表 |
| `design_experiment` | Markdown 设计矩阵表格 |
| `analyze_experiment` | Markdown ANOVA 表 (效应/系数/p值/显著性) |
| `get_process_knowledge` | Markdown 工艺参数表 + 规则列表 |
| `generate_report` | 保持 Markdown (已实现) |

**文件**: `src/process_opt/agent/tools/analysis_tools.py` (8+ 工具函数)

---

## 9. 错误处理增强

### 9a. SUGGESTIONS 补全
**文件**: `src/process_opt/api/app.py`

补全 8 个 `AnalysisError` 错误码的 `SUGGESTIONS` 映射:
```
INVALID_PARAMS, DATASET_NOT_FOUND, DEVICE_NOT_FOUND, RECORD_NOT_FOUND,
NO_DATA, TOO_FEW_POINTS, COMPUTATION_FAILED, FEATURE_MISMATCH
```

### 9b. Agent 工具重试
**文件**: `src/process_opt/agent/tools/analysis_tools.py`

为所有数据库/计算密集型工具增加一次重试（1 retry）：
- `query_records`, `get_stats`, `trace_product` (DB 查询类)
- `analyze_correlation`, `run_regression`, `run_spc`, `recommend_params` (计算类)

装饰器模式:
```python
def with_retry(max_retries=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning("tool %s retry %d: %s", func.__name__, attempt + 1, e)
            raise last_error
        return wrapper
    return decorator
```

---

## 实施策略

按复杂度递增顺序执行：
1. 先做低复杂度项 (1, 4, 5, 9) — 快速收益
2. 再做中复杂度项 (2, 3, 6, 8) — 核心改进
3. 最后做高复杂度项 (7) — 涉及 DB schema 变更
