# Agent 系统数据集成分析能力 — 设计文档

**日期**: 2026-06-18
**目标**: Agent 通过工具调用方式覆盖系统全部 REST API 端点的**查询和审批**能力，实现对产线、设备、参数、分析、实验数据的集成分析。

## 1. 设计决策

- **方案**: 扩展工具模块（遵循现有 `@tool` → Service 对象模式）
- **开放范围**: 读操作全部开放 + 参数审批流程（submit/approve/reject），不开放产线/设备的创建/删除
- **输出格式**: 每个工具按自身场景选择最合适的 Markdown 格式（与现有模式一致）
- **actor 字段**: 审批操作使用 `"agent"` 作为 actor

## 2. 模块架构

新增工具分布在 4 个模块，每个模块导出 `create_xxx_tools(...)` 工厂函数：

```
src/process_opt/agent/tools/
├── analysis_tools.py   # 现有 17 个工具 + 新增 4 个分析增强工具
├── system_tools.py     # 新建：产线查询、设备查询、产线监控 (5 个)
├── parameter_tools.py  # 新建：参数集查询 + 审批流程 (6 个)
└── experiment_tools.py # 新建：实验方案列表 (1 个)
```

在 `main.py` 中合并所有工具：

```python
tools = (
    create_analysis_tools(repo, analysis, params, knowledge, experiment) +
    create_system_tools(line_device_repo, analysis_service) +
    create_parameter_tools(parameter_service) +
    create_experiment_tools(experiment_repo)
)
```

### 依赖注入

`main.py` 中已有全部所需代理对象，新工厂函数需要的额外参数：

| 工厂函数 | 额外依赖 |
|---|---|
| `create_system_tools` | `line_device_repo_proxy`, `analysis_service_proxy` |
| `create_parameter_tools` | `parameter_service_proxy` |
| `create_experiment_tools` | `experiment_repo_proxy` |

## 3. 工具清单

### 3.1 system_tools.py — 产线 & 设备查询（5 个）

| # | 工具名 | 对应 API | 功能描述 |
|---|---|---|---|
| 1 | `list_production_lines` | `GET /api/v1/lines` | 列出所有产线，含设备数量、负责人、位置 |
| 2 | `get_production_line` | `GET /api/v1/lines/{line_id}` | 单个产线详情 + 下属设备列表 |
| 3 | `list_registered_devices` | `GET /api/v1/devices` | 设备注册列表，可按 line_id 过滤 |
| 4 | `get_registered_device` | `GET /api/v1/devices/{device_id}` | 单个设备详情（名称、类型、图标、所属产线） |
| 5 | `monitor_production_line` | `GET /api/v1/lines/{line_id}/monitor` | 产线级 SPC 监控总览：各设备状态(正常/异常/临界)、最差 Cpk、异常数、产线整体评级 |

**不开放**: create_line, update_line, delete_line, update_device, delete_device, reorder_devices

工具签名示例：
```python
@tool
async def list_production_lines() -> str:
    """列出所有产线信息。返回产线名称、负责人、位置、设备数量。"""

@tool
async def monitor_production_line(line_id: str) -> str:
    """对产线进行 SPC 监控总览。返回各设备的过程能力状态和产线整体评级。"""
```

`monitor_production_line` 内部调用 `analysis_service.spc()` 为产线下每个设备计算 SPC，汇总为产线级报告。依赖 `analysis_service` 参数。

### 3.2 parameter_tools.py — 参数集查询 & 审批（6 个）

| # | 工具名 | 对应 API | 功能描述 |
|---|---|---|---|
| 6 | `list_parameter_sets` | `GET /api/v1/parameters/sets` | 参数集列表，可按 device_type 过滤，显示状态和版本 |
| 7 | `get_parameter_set` | `GET /api/v1/parameters/sets/{set_id}` | 单个参数集详情，含所有参数项(key/value/unit) |
| 8 | `get_latest_active_parameters` | `GET /api/v1/parameters/latest` | 获取指定 device_type 当前激活的参数集及其参数项 |
| 9 | `submit_parameter_set` | `POST .../sets/{set_id}/submit` | 提交参数集进入审批 (draft→proposed)，可选备注 |
| 10 | `approve_parameter_set` | `POST .../sets/{set_id}/approve` | 批准参数集 (proposed→approved)，可选备注 |
| 11 | `reject_parameter_set` | `POST .../sets/{set_id}/reject` | 驳回参数集 (proposed→rejected)，建议附带驳回原因 |

**不开放**: create_draft（由推荐流程自动创建）、activate（需要设备确认流程）

**注意**: 现有 `analysis_tools.py` 中已有 `get_parameters` 工具（按 device_type 列出参数集）。实现时删除 `get_parameters`，由 `list_parameter_sets` 替代，两者功能重复。

审批工具签名示例：
```python
@tool
async def submit_parameter_set(set_id: int, note: str = "") -> str:
    """提交参数集进入审批流程。set_id: 参数集ID。note: 可选备注。"""

@tool
async def approve_parameter_set(set_id: int, note: str = "") -> str:
    """批准参数集。set_id: 参数集ID。note: 可选审批意见。"""

@tool
async def reject_parameter_set(set_id: int, note: str = "") -> str:
    """驳回参数集。set_id: 参数集ID。note: 驳回原因（建议填写）。"""
```

actor 参数当前硬编码为 `"agent"`。审批操作的输出格式：返回操作结果 + 参数集当前状态 + 参数项摘要表格。

### 3.3 analysis_tools.py — 新增 4 个分析增强工具

在现有 17 个工具基础上追加：

| # | 工具名 | 对应 API | 功能描述 |
|---|---|---|---|
| 12 | `analyze_importance` | `POST .../analysis/importance` | 特征重要性分析（Random Forest），识别对质量指标影响最大的参数排序 |
| 13 | `optimize_parameters` | `POST .../analysis/optimize` | 多目标优化，在约束条件下寻找同时满足多个质量目标的最优参数 |
| 14 | `trace_product_full` | `GET .../analysis/trace/{barcode}` | 完整产品追溯：工艺参数 + 检测结果 + 当前有效参数集对比 |
| 15 | `preview_dataset` | `GET .../analysis/dataset/{id}/preview` | 预览数据集内容（表格分页），查看字段统计信息 |

**与现有工具的差异**：
- `trace_product_full` 比现有 `trace_product` 多了"当前有效参数集"列，可直观对比实际参数 vs 标准参数
- `analyze_importance` 和 `optimize_parameters` 需要先有 `dataset_id`，工具内部通过 `excel.get_dataset()` 获取数据后调用分析函数

### 3.4 experiment_tools.py — 实验管理查询（1 个）

| # | 工具名 | 对应 API | 功能描述 |
|---|---|---|---|
| 16 | `list_experiment_plans` | `GET /api/v1/experiment/plans` | 列出所有实验方案，含方法、状态、运行次数、创建时间 |

现有的 `save_experiment_plan`、`record_experiment_result_for_plan`、`get_experiment_results`、`analyze_experiment` 保持在 `analysis_tools.py` 中不变。

## 4. 工具实现模式

所有新工具遵循现有模式：

```python
@tool
@with_retry()  # 可选，对可能失败的操作使用
async def tool_name(param: type) -> str:
    """中文描述工具功能。param: 参数说明。"""
    # 1. 调用 Service/Repository 代理
    result = await service.method(params)

    # 2. 格式化为 Markdown 字符串
    lines = ["## 结果标题", ""]
    lines.append("| 列1 | 列2 |")
    lines.append("|-----|-----|")
    for item in result:
        lines.append(f"| {item.field1} | {item.field2} |")

    # 3. 返回格式化的字符串供 LLM 直接展示
    return "\n".join(lines)
```

关键约束：
- 永远返回 Markdown 字符串（不返回 JSON）
- 错误信息返回可读的中文提示
- `@with_retry()` 用于可能因数据库连接等临时错误失败的操作
- 查询类工具不需要重试（失败的查询应直接报错）

## 5. main.py 变更摘要

需修改 `create_api_app_from_settings()` 中的工具创建部分：

```python
# Before
tools = create_analysis_tools(
    repository_proxy, analysis_service_proxy, parameter_service_proxy,
    knowledge_loader, experiment_repo_proxy,
)

# After
from process_opt.agent.tools.system_tools import create_system_tools
from process_opt.agent.tools.parameter_tools import create_parameter_tools
from process_opt.agent.tools.experiment_tools import create_experiment_tools

tools = (
    create_analysis_tools(
        repository_proxy, analysis_service_proxy, parameter_service_proxy,
        knowledge_loader, experiment_repo_proxy,
    ) +
    create_system_tools(line_device_repo_proxy, analysis_service_proxy) +
    create_parameter_tools(parameter_service_proxy) +
    create_experiment_tools(experiment_repo_proxy)
)
```

## 6. 测试策略

- 新增模块各自编写单元测试：`tests/agent/test_system_tools.py`、`tests/agent/test_parameter_tools.py`、`tests/agent/test_experiment_tools.py`
- 使用 mock Service/Repository 对象，验证工具函数输出格式
- 对审批类工具测试状态转换合法性（如尝试 approve 一个 draft 状态应返回错误）
- analysis_tools 新增的 4 个工具在现有 `tests/analysis/` 测试基础上扩展
