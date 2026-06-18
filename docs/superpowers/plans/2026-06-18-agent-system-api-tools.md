# Agent 系统数据集成分析能力 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 16 new LangChain tools across 4 modules to give the agent full read + approval access to all system REST API endpoints.

**Architecture:** Three new tool modules (`system_tools.py`, `parameter_tools.py`, `experiment_tools.py`) plus 4 new tools added to existing `analysis_tools.py`. Each module exports a `create_xxx_tools(...)` factory function called from `main.py`. All tools call Service/Repository proxy objects directly (no HTTP), format results as Markdown strings.

**Tech Stack:** LangChain `@tool` decorator, Python async, existing `process_opt` service/repository layer

**Spec:** [2026-06-18-agent-system-api-tools-design.md](../specs/2026-06-18-agent-system-api-tools-design.md)

## Global Constraints

- Open only read operations + parameter approval workflow (submit/approve/reject)
- Do NOT open: line/device create/update/delete, parameter activate/create_draft
- All tools return Markdown strings (never JSON)
- Use `@with_retry()` only for operations that may fail due to transient DB errors
- actor field for approvals hardcoded as `"agent"`
- Remove existing `get_parameters` tool (replaced by `list_parameter_sets`)
- Follow existing tool patterns in `analysis_tools.py`

## File Structure

```
src/process_opt/agent/tools/
├── analysis_tools.py   # MODIFY: remove get_parameters, add 4 tools
├── system_tools.py     # CREATE: 5 tools
├── parameter_tools.py  # CREATE: 6 tools
└── experiment_tools.py # CREATE: 1 tool

src/process_opt/api/
└── main.py             # MODIFY: import new factories, merge tool lists

tests/agent/
├── test_system_tools.py      # CREATE
├── test_parameter_tools.py   # CREATE
└── test_experiment_tools.py  # CREATE
```

---

### Task 1: Create system_tools.py

**Files:**
- Create: `src/process_opt/agent/tools/system_tools.py`

**Interfaces:**
- Consumes: `LineDeviceRepositoryProtocol` (list_lines, get_line, list_devices, get_device, get_devices_by_line), `AnalysisService` (spc)
- Produces: `create_system_tools(line_device_repo, analysis_service=None) -> list`

- [ ] **Step 1: Write the module**

```python
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from process_opt.analysis.schemas import SpcRequest


def create_system_tools(
    line_device_repo: Any,
    analysis_service: Any = None,
) -> list:
    @tool
    async def list_production_lines() -> str:
        """列出所有产线信息。返回每条产线的名称、负责人、位置、设备数量。"""
        lines = await line_device_repo.list_lines()
        if not lines:
            return "当前系统没有注册的产线。"

        result = ["## 产线列表", ""]
        result.append(f"共 **{len(lines)}** 条产线：")
        result.append("")
        result.append("| 产线名称 | 负责人 | 位置 | 设备数 |")
        result.append("|----------|--------|------|--------|")
        for line in lines:
            result.append(
                f"| {line.get('name', '-')} | {line.get('responsible', '-')} | "
                f"{line.get('location', '-')} | {line.get('device_count', 0)} |"
            )
        return "\n".join(result)

    @tool
    async def get_production_line(line_id: str) -> str:
        """获取单条产线的详细信息，包含下属设备列表。line_id: 产线ID。"""
        line = await line_device_repo.get_line(line_id)
        if line is None:
            return f"未找到产线 `{line_id}`。"

        devices = await line_device_repo.list_devices(line_id=line_id)

        result = [
            f"## 产线详情: {line.get('name', line_id)}",
            "",
            f"- **负责人**: {line.get('responsible', '-')}",
            f"- **位置**: {line.get('location', '-')}",
            f"- **设备数量**: {len(devices)}",
        ]

        if devices:
            result.append("")
            result.append("### 下属设备")
            result.append("| 设备ID | 名称 | 类型 | 描述 |")
            result.append("|--------|------|------|------|")
            for d in devices:
                result.append(
                    f"| {d.get('id', '-')} | {d.get('name', '-')} | "
                    f"{d.get('type', '-')} | {d.get('description', '-')} |"
                )
        return "\n".join(result)

    @tool
    async def list_registered_devices(line_id: str = "") -> str:
        """列出系统中注册的所有设备。可选按产线过滤。line_id: 产线ID（可选，留空查全部）。"""
        lid = line_id if line_id else None
        devices = await line_device_repo.list_devices(line_id=lid)

        if not devices:
            return "当前系统没有注册的设备。"

        header = f"## 设备列表 (共 {len(devices)} 台)"
        if lid:
            header += f" — 产线 {lid}"

        result = [header, ""]
        result.append("| 设备ID | 名称 | 类型 | 所属产线 |")
        result.append("|--------|------|------|----------|")
        for d in devices:
            result.append(
                f"| {d.get('id', '-')} | {d.get('name', '-')} | "
                f"{d.get('type', '-')} | {d.get('line_name', '-')} |"
            )
        return "\n".join(result)

    @tool
    async def get_registered_device(device_id: str) -> str:
        """获取单个设备的详细信息。device_id: 设备ID。"""
        device = await line_device_repo.get_device(device_id)
        if device is None:
            return f"未找到设备 `{device_id}`。"

        result = [
            f"## 设备详情: {device.get('name', device_id)}",
            "",
            f"- **设备ID**: {device.get('id', '-')}",
            f"- **名称**: {device.get('name', '-')}",
            f"- **类型**: {device.get('type', '-')}",
            f"- **所属产线**: {device.get('line_name', '-')}",
            f"- **描述**: {device.get('description', '-')}",
        ]
        return "\n".join(result)

    @tool
    async def monitor_production_line(line_id: str) -> str:
        """对整条产线进行 SPC 监控总览。line_id: 产线ID。返回各设备的过程能力状态和产线整体评级。"""
        if analysis_service is None:
            return "SPC 分析服务不可用，无法监控产线。"

        line = await line_device_repo.get_line(line_id)
        if line is None:
            return f"未找到产线 `{line_id}`。"

        devices = await line_device_repo.list_devices(line_id=line_id)
        if not devices:
            return f"产线 `{line.get('name', line_id)}` 下没有注册设备。"

        device_summaries: list[dict] = []
        normal = abnormal = marginal = no_spec = 0

        for device in devices:
            try:
                spc_result = await analysis_service.spc(SpcRequest(
                    device_id=device["id"],
                ))
            except Exception:
                device_summaries.append({
                    "device_id": device["id"],
                    "device_name": device.get("name", device["id"]),
                    "type": device.get("type", "-"),
                    "status": "error",
                    "worst_cpk": None,
                    "param_count": 0,
                    "outlier_total": 0,
                })
                continue

            if not spc_result.overview:
                continue

            statuses = [ov.status for ov in spc_result.overview]
            if "abnormal" in statuses:
                dev_status = "abnormal"
            elif "marginal" in statuses:
                dev_status = "marginal"
            elif "no_spec" in statuses:
                dev_status = "no_spec"
            else:
                dev_status = "normal"

            cpks = [ov.cpk for ov in spc_result.overview if ov.cpk is not None]
            device_summaries.append({
                "device_id": device["id"],
                "device_name": device.get("name", device["id"]),
                "type": device.get("type", "-"),
                "status": dev_status,
                "worst_cpk": round(min(cpks), 2) if cpks else None,
                "param_count": len(spc_result.overview),
                "outlier_total": sum(ov.outlier_count for ov in spc_result.overview),
            })

            if dev_status == "abnormal":
                abnormal += 1
            elif dev_status == "marginal":
                marginal += 1
            elif dev_status == "no_spec":
                no_spec += 1
            else:
                normal += 1

        if abnormal > 0:
            line_status = "❌ 异常"
        elif marginal > 0:
            line_status = "⚠ 临界"
        elif no_spec > 0:
            line_status = "⚪ 无规格"
        elif normal > 0:
            line_status = "✅ 正常"
        else:
            line_status = "— 无数据"

        status_emoji = {"normal": "✅", "abnormal": "❌", "marginal": "⚠", "no_spec": "⚪", "error": "💥"}

        result = [
            f"## 产线监控: {line.get('name', line_id)}",
            "",
            f"**整体状态**: {line_status}",
            f"- 正常: {normal} | 异常: {abnormal} | 临界: {marginal} | 无规格: {no_spec}",
            "",
            "| 设备 | 类型 | 状态 | 最差Cpk | 参数数 | 异常数 |",
            "|------|------|------|---------|--------|--------|",
        ]
        for d in device_summaries:
            emoji = status_emoji.get(d["status"], "—")
            cpk_str = f"{d['worst_cpk']}" if d["worst_cpk"] is not None else "N/A"
            result.append(
                f"| {d['device_name']} | {d['type']} | {emoji} {d['status']} | "
                f"{cpk_str} | {d['param_count']} | {d['outlier_total']} |"
            )

        return "\n".join(result)

    return [
        list_production_lines,
        get_production_line,
        list_registered_devices,
        get_registered_device,
        monitor_production_line,
    ]
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "import ast; ast.parse(open('src/process_opt/agent/tools/system_tools.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/system_tools.py
git commit -m "feat: add system query tools (lines, devices, line monitor)"
```

---

### Task 2: Create parameter_tools.py

**Files:**
- Create: `src/process_opt/agent/tools/parameter_tools.py`

**Interfaces:**
- Consumes: `ParameterService` (list_sets, get_set_with_items, get_latest, submit, approve, reject)
- Produces: `create_parameter_tools(parameter_service) -> list`

- [ ] **Step 1: Write the module**

```python
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool


def create_parameter_tools(parameter_service: Any) -> list:
    @tool
    async def list_parameter_sets(device_type: str = "") -> str:
        """列出所有参数集。可选按 device_type 过滤。
        device_type: 可选，按设备类型过滤（如 adhesive_curing, injection_molding 等）。"""
        sets = await parameter_service.list_sets()
        if device_type:
            sets = [s for s in sets if getattr(s, "device_type", "") == device_type]

        if not sets:
            dtype_info = f" (类型: {device_type})" if device_type else ""
            return f"当前系统没有参数集{dtype_info}。"

        result = [f"## 参数集列表 (共 {len(sets)} 个)", ""]
        result.append("| ID | 名称 | 设备类型 | 版本 | 状态 | 创建者 |")
        result.append("|----|------|----------|------|------|--------|")
        for s in sets:
            status = getattr(s, "status", "unknown")
            status_emoji = {
                "draft": "📝", "proposed": "⏳", "approved": "✅",
                "rejected": "❌", "active": "🟢", "archived": "📦",
            }.get(status, "")
            result.append(
                f"| {s.id} | {s.name} | {s.device_type} | "
                f"v{s.version} | {status_emoji} {status} | {s.created_by} |"
            )
        return "\n".join(result)

    @tool
    async def get_parameter_set(set_id: int) -> str:
        """获取单个参数集的完整详情，包含所有参数项及其值。set_id: 参数集ID。"""
        ps = await parameter_service.get_set_with_items(set_id)
        if ps is None:
            return f"未找到参数集 `{set_id}`。"

        s = ps.parameter_set
        result = [
            f"## 参数集: {s.name}",
            "",
            f"- **ID**: {s.id}",
            f"- **设备类型**: {s.device_type}",
            f"- **版本**: v{s.version}",
            f"- **状态**: {s.status}",
            f"- **创建者**: {s.created_by}",
            f"- **备注**: {s.note or '-'}",
            "",
            "### 参数项",
            "| 参数键 | 值 | 单位 | 数据类型 |",
            "|--------|-----|------|----------|",
        ]
        for item in ps.items:
            val = item.param_value
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            result.append(
                f"| {item.param_key} | {val} | {item.unit or '-'} | {item.data_type} |"
            )
        return "\n".join(result)

    @tool
    async def get_latest_active_parameters(device_type: str) -> str:
        """获取指定设备类型当前激活（active）的参数集及其所有参数项。
        device_type: 设备类型标识（如 adhesive_curing, injection_molding 等）。"""
        ps = await parameter_service.get_latest(device_type)
        if ps is None:
            return f"设备类型 `{device_type}` 没有激活的参数集。"

        s = ps.parameter_set
        result = [
            f"## 当前激活参数: {s.name}",
            "",
            f"- **设备类型**: {s.device_type}",
            f"- **版本**: v{s.version}",
            f"- **激活时间**: {s.activated_at or '-'}",
            "",
            "| 参数键 | 当前值 | 单位 | 数据类型 |",
            "|--------|--------|------|----------|",
        ]
        for item in ps.items:
            val = item.param_value
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            result.append(
                f"| {item.param_key} | {val} | {item.unit or '-'} | {item.data_type} |"
            )
        return "\n".join(result)

    @tool
    async def submit_parameter_set(set_id: int, note: str = "") -> str:
        """提交参数集进入审批流程（draft → proposed）。set_id: 参数集ID。note: 可选备注。"""
        try:
            ps = await parameter_service.submit(set_id, actor="agent", note=note or None)
            return (
                f"✅ 参数集 `{ps.name}` (ID: {ps.id}) 已提交审批。\n"
                f"状态: {ps.status} | 版本: v{ps.version}"
            )
        except Exception as e:
            return f"❌ 提交失败: {e}"

    @tool
    async def approve_parameter_set(set_id: int, note: str = "") -> str:
        """批准参数集（proposed → approved）。set_id: 参数集ID。note: 可选审批意见。"""
        try:
            ps = await parameter_service.approve(set_id, actor="agent", note=note or None)
            return (
                f"✅ 参数集 `{ps.name}` (ID: {ps.id}) 已批准。\n"
                f"状态: {ps.status} | 版本: v{ps.version}"
            )
        except Exception as e:
            return f"❌ 批准失败: {e}"

    @tool
    async def reject_parameter_set(set_id: int, note: str = "") -> str:
        """驳回参数集（proposed → rejected）。set_id: 参数集ID。note: 驳回原因（建议填写）。"""
        try:
            ps = await parameter_service.reject(set_id, actor="agent", note=note or None)
            return (
                f"❌ 参数集 `{ps.name}` (ID: {ps.id}) 已驳回。\n"
                f"状态: {ps.status} | 版本: v{ps.version}\n"
                f"驳回原因: {note or '未提供'}"
            )
        except Exception as e:
            return f"❌ 驳回操作失败: {e}"

    return [
        list_parameter_sets,
        get_parameter_set,
        get_latest_active_parameters,
        submit_parameter_set,
        approve_parameter_set,
        reject_parameter_set,
    ]
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "import ast; ast.parse(open('src/process_opt/agent/tools/parameter_tools.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/parameter_tools.py
git commit -m "feat: add parameter query and approval tools"
```

---

### Task 3: Create experiment_tools.py

**Files:**
- Create: `src/process_opt/agent/tools/experiment_tools.py`

**Interfaces:**
- Consumes: experiment_repo (list_plans)
- Produces: `create_experiment_tools(experiment_repo) -> list`

- [ ] **Step 1: Write the module**

```python
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


def create_experiment_tools(experiment_repo: Any) -> list:
    @tool
    async def list_experiment_plans(limit: int = 20) -> str:
        """列出所有实验方案。limit: 返回数量上限（默认20）。
        返回实验方案的名称、方法、状态、运行次数和创建时间。"""
        plans = await experiment_repo.list_plans(limit)

        if not plans:
            return "当前系统没有实验方案。"

        result = [f"## 实验方案列表 (共 {len(plans)} 个)", ""]
        result.append("| ID | 名称 | 工艺 | 方法 | 状态 | 创建者 | 创建时间 |")
        result.append("|----|------|------|------|------|--------|----------|")
        for p in plans:
            status_emoji = {
                "draft": "📝", "in_progress": "🔄",
                "completed": "✅", "archived": "📦",
            }.get(p.status, "")
            created = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "-"
            result.append(
                f"| {p.id} | {p.name} | {p.process_type} | "
                f"{p.method} | {status_emoji} {p.status} | "
                f"{p.created_by} | {created} |"
            )
        return "\n".join(result)

    return [list_experiment_plans]
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "import ast; ast.parse(open('src/process_opt/agent/tools/experiment_tools.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/agent/tools/experiment_tools.py
git commit -m "feat: add experiment plan listing tool"
```

---

### Task 4: Modify analysis_tools.py — remove get_parameters, add 4 tools

**Files:**
- Modify: `src/process_opt/agent/tools/analysis_tools.py`

**Changes:**
1. Remove the `get_parameters` tool definition (existing lines ~242-249)
2. Remove `get_parameters` from the `tool_list`
3. Add `analyze_importance`, `optimize_parameters`, `trace_product_full`, `preview_dataset` tools
4. Add them to `tool_list`

- [ ] **Step 1: Remove get_parameters**

In `src/process_opt/agent/tools/analysis_tools.py`, find and delete the `get_parameters` tool block:

```python
    @tool
    async def get_parameters(device_type: str = "") -> str:
        """获取参数集列表。可指定 device_type 过滤。"""
        ...
```

Also remove `get_parameters` from the `tool_list` list at the bottom.

- [ ] **Step 2: Add 4 new tool definitions**

Insert before the `tool_list = [` line:

```python
    @tool
    async def analyze_importance(dataset_id: str, target_field: str) -> str:
        """分析各特征参数对目标质量指标的重要性排序。使用随机森林模型计算特征重要性。
        dataset_id: 数据集ID（通过 build_dataset 获取）。
        target_field: 目标质量指标字段名。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.importance import compute_importance

        ds = get_dataset(dataset_id)
        if ds is None:
            return "数据集未找到或已过期，请重新构建数据集。"

        feature_fields = sorted({k for f in ds.features for k in f})
        if not feature_fields:
            return "数据集中没有可用于重要性分析的特征字段。"

        result = compute_importance(ds, feature_fields, target_field)

        sorted_items = sorted(
            result.importances.items(), key=lambda x: x[1], reverse=True
        )
        total = sum(v for _, v in sorted_items)
        lines = [
            f"## 特征重要性分析: {target_field}",
            f"**方法**: {result.method} | **特征数**: {len(feature_fields)}",
            "",
            "| 排名 | 参数 | 重要性 | 占比 |",
            "|------|------|--------|------|",
        ]
        for rank, (field, imp) in enumerate(sorted_items, 1):
            pct = (imp / total * 100) if total > 0 else 0
            lines.append(f"| {rank} | {field} | {imp:.4f} | {pct:.1f}% |")
        return "\n".join(lines)

    @tool
    async def optimize_parameters(
        dataset_id: str,
        target_field: str,
        usl: float,
        lsl: float,
        target_value: float,
        key_factors_json: str,
        step_size: float = 0.1,
        target_cpk: float = 1.33,
        max_iterations: int = 5000,
    ) -> str:
        """多目标优化：在约束条件下寻找最优参数组合以最大化过程能力。
        dataset_id: 数据集ID（通过 build_dataset 获取）。
        target_field: 优化目标的质量指标字段名。
        usl: 规格上限。
        lsl: 规格下限。
        target_value: 目标值。
        key_factors_json: 要优化的关键因子列表，JSON数组格式，如 ["temp","pressure"]。
        step_size: 搜索步长（默认0.1）。
        target_cpk: 目标Cpk值（默认1.33）。
        max_iterations: 最大迭代次数（默认5000）。"""
        import json as _json
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.optimization import run_optimization
        from process_opt.analysis.schemas import OptimizationConfig

        ds = get_dataset(dataset_id)
        if ds is None:
            return "数据集未找到或已过期，请重新构建数据集。"

        key_factors = _json.loads(key_factors_json)
        if not isinstance(key_factors, list) or not key_factors:
            return "key_factors_json 必须是非空的 JSON 数组，如 [\"temp\",\"pressure\"]。"

        config = OptimizationConfig(
            dataset_id=dataset_id,
            target_field=target_field,
            usl=usl,
            lsl=lsl,
            target_value=target_value,
            target_cpk=target_cpk,
            key_factors=key_factors,
            step_size=step_size,
            max_iterations=max_iterations,
        )
        result = run_optimization(ds, config)

        lines = [
            "## 参数优化结果",
            "",
            f"**目标指标**: {target_field}",
            f"**初始 Cpk**: {result.initial_cpk:.4f} → **优化后 Cpk**: {result.optimized_cpk:.4f}",
            "",
            "### 推荐参数调整",
            "| 参数 | 推荐值 | 调整幅度 |",
            "|------|--------|----------|",
        ]
        for param, adj in result.parameter_adjustments.items():
            delta = adj.get("delta", 0)
            if isinstance(delta, (int, float)):
                direction = f"{delta:+.2f}"
            else:
                direction = str(delta)
            rec_val = result.recommended_params.get(param, "N/A")
            lines.append(f"| {param} | {rec_val} | {direction} |")

        if result.convergence:
            lines.append("")
            lines.append(f"**收敛**: {len(result.convergence)} 次迭代后收敛")

        return "\n".join(lines)

    @tool
    async def trace_product_full(barcode: str) -> str:
        """完整追溯单个产品（barcode）的生产链路。
        返回工艺参数、检测结果、以及当前有效参数集的对照。
        barcode: 产品条码。"""
        record = await repository.get_analysis_record(barcode)
        if record is None:
            return f"未找到条码 `{barcode}` 的生产记录。"

        params = record.get("params", {})
        if isinstance(params, str):
            import json as _json
            params = _json.loads(params)

        inspection = record.get("inspection_result", {})
        if isinstance(inspection, str):
            import json as _json
            inspection = _json.loads(inspection)

        result = [
            f"## 产品追溯: {barcode}",
            "",
            f"- **设备**: {record.get('device_id', '-')}",
            f"- **生产时间**: {record.get('processed_at', '-')}",
            "",
            "### 工艺参数（实际值）",
            "| 参数 | 实际值 |",
            "|------|--------|",
        ]
        for k, v in params.items():
            result.append(f"| {k} | {v} |")

        result.append("")
        result.append("### 检测结果")
        result.append("| 指标 | 结果 |")
        result.append("|------|------|")
        if isinstance(inspection, list):
            for item in inspection:
                if isinstance(item, dict):
                    result.append(
                        f"| {item.get('name', '-')} | "
                        f"{item.get('value', item.get('result', '-'))} |"
                    )
        elif isinstance(inspection, dict):
            for k, v in inspection.items():
                result.append(f"| {k} | {v} |")

        # Compare with active parameter set
        device_id = record.get("device_id", "")
        if device_id and parameter_service is not None:
            try:
                device_type = record.get("product_model", "adhesive_curing")
                latest = await parameter_service.get_latest(device_type)
                if latest is not None:
                    result.append("")
                    result.append("### 当前激活参数集（标准值对照）")
                    result.append("| 参数 | 实际值 | 标准值 | 偏差 |")
                    result.append("|------|--------|--------|------|")
                    for item in latest.items:
                        actual = params.get(item.param_key, "N/A")
                        standard = item.param_value
                        deviation = ""
                        if isinstance(actual, (int, float)) and isinstance(standard, (int, float)):
                            deviation = f"{actual - standard:.2f}"
                        result.append(
                            f"| {item.param_key} | {actual} | {standard} | {deviation} |"
                        )
            except Exception:
                pass

        return "\n".join(result)

    @tool
    async def preview_dataset(dataset_id: str, page: int = 1, size: int = 20) -> str:
        """预览数据集的内容，分页展示数据行和字段统计信息。
        dataset_id: 数据集ID（通过 build_dataset 或文件上传获取）。
        page: 页码（从1开始）。
        size: 每页行数（默认20）。"""
        from process_opt.analysis.excel import get_dataset

        ds = get_dataset(dataset_id)
        if ds is None:
            return "数据集未找到或已过期，请重新构建数据集。"

        feature_names = sorted({k for f in ds.features for k in f})
        target_names = sorted({k for t in ds.targets for k in t})
        all_columns = feature_names + target_names

        total = ds.sample_count
        start = (page - 1) * size
        end = min(start + size, total)

        lines = [
            f"## 数据集预览",
            f"**总行数**: {total} | **特征字段**: {len(feature_names)} | **目标字段**: {len(target_names)}",
            f"**当前页**: {page} (第 {start + 1}-{end} 行)",
            "",
        ]

        if ds.field_summary:
            lines.append("### 字段统计")
            lines.append("| 字段 | 样本数 | 均值 | 最小值 | 最大值 |")
            lines.append("|------|--------|------|--------|--------|")
            for fn in all_columns:
                s = ds.field_summary.get(fn, {})
                mean_v = f"{s.get('mean', 0):.3f}" if s.get('mean') is not None else "N/A"
                min_v = f"{s.get('min', 0):.3f}" if s.get('min') is not None else "N/A"
                max_v = f"{s.get('max', 0):.3f}" if s.get('max') is not None else "N/A"
                lines.append(f"| {fn} | {s.get('count', 0)} | {mean_v} | {min_v} | {max_v} |")

        lines.append("")
        lines.append(f"### 数据行 (第 {page} 页)")
        header = "| # | " + " | ".join(all_columns) + " |"
        sep = "|---|" + "|".join(["------"] * len(all_columns)) + "|"
        lines.append(header)
        lines.append(sep)

        for i in range(start, end):
            row_parts = [str(i + 1)]
            for fn in all_columns:
                val = "N/A"
                if i < len(ds.features) and fn in ds.features[i]:
                    val = ds.features[i][fn]
                elif i < len(ds.targets) and fn in ds.targets[i]:
                    val = ds.targets[i][fn]
                if isinstance(val, float):
                    val = f"{val:.4f}"
                row_parts.append(str(val))
            lines.append("| " + " | ".join(row_parts) + " |")

        return "\n".join(lines)
```

- [ ] **Step 3: Update tool_list**

At the bottom of `create_analysis_tools()`, update the `tool_list`:

```python
    tool_list = [
        query_records, get_devices, get_stats, profile_data,
        analyze_correlation, analyze_pareto, run_regression,
        recommend_params, run_spc,
        # get_parameters removed — use list_parameter_sets from parameter_tools
        get_process_knowledge, build_dataset,
        design_experiment, analyze_experiment,
        analyze_importance, optimize_parameters,
        trace_product_full, preview_dataset,
    ]
```

Also keep the conditional experiment tools (save_experiment_plan, etc.) and trace_product, upload_and_analyze, generate_report as-is.

- [ ] **Step 4: Commit**

```bash
git add src/process_opt/agent/tools/analysis_tools.py
git commit -m "feat: add importance, optimization, full trace, dataset preview tools; remove get_parameters"
```

---

### Task 5: Wire up main.py

**Files:**
- Modify: `src/process_opt/api/main.py`

- [ ] **Step 1: Add new imports**

Find the import of `create_analysis_tools` and add:

```python
from process_opt.agent.tools.analysis_tools import create_analysis_tools
from process_opt.agent.tools.system_tools import create_system_tools
from process_opt.agent.tools.parameter_tools import create_parameter_tools
from process_opt.agent.tools.experiment_tools import create_experiment_tools
```

- [ ] **Step 2: Replace tools creation block**

Replace:

```python
    tools = create_analysis_tools(
        repository_proxy, analysis_service_proxy, parameter_service_proxy, knowledge_loader,
        experiment_repo_proxy,
    )
```

With:

```python
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

- [ ] **Step 3: Commit**

```bash
git add src/process_opt/api/main.py
git commit -m "feat: wire up system, parameter, experiment tools in main.py"
```

---

### Task 6: Write tests for system_tools

**Files:**
- Create: `tests/agent/test_system_tools.py`

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations

import pytest

from process_opt.agent.tools.system_tools import create_system_tools


class MockLineDeviceRepo:
    def __init__(self) -> None:
        self._lines = [
            {"id": "L1", "name": "产线A", "responsible": "张三", "location": "一楼", "device_count": 2},
            {"id": "L2", "name": "产线B", "responsible": "李四", "location": "二楼", "device_count": 1},
        ]
        self._devices = [
            {"id": "D1", "name": "注塑机1", "type": "injection_molding", "line_name": "产线A", "line_id": "L1", "description": "主注塑机"},
            {"id": "D2", "name": "检测站1", "type": "inspection", "line_name": "产线A", "line_id": "L1", "description": "QA检测"},
            {"id": "D3", "name": "固化炉1", "type": "adhesive_curing", "line_name": "产线B", "line_id": "L2", "description": ""},
        ]

    async def list_lines(self) -> list[dict]:
        return self._lines

    async def get_line(self, line_id: str) -> dict | None:
        for line in self._lines:
            if line["id"] == line_id:
                return line
        return None

    async def list_devices(self, line_id: str | None = None) -> list[dict]:
        if line_id is None:
            return self._devices
        return [d for d in self._devices if d.get("line_id") == line_id]

    async def get_device(self, device_id: str) -> dict | None:
        for d in self._devices:
            if d["id"] == device_id:
                return d
        return None


@pytest.fixture
def tools() -> list:
    repo = MockLineDeviceRepo()
    return create_system_tools(repo, analysis_service=None)


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


@pytest.mark.asyncio
async def test_list_production_lines(tools: list) -> None:
    tool = _find_tool(tools, "list_production_lines")
    result = await tool.ainvoke({})
    assert "产线A" in result
    assert "产线B" in result
    assert "张三" in result


@pytest.mark.asyncio
async def test_get_production_line_found(tools: list) -> None:
    tool = _find_tool(tools, "get_production_line")
    result = await tool.ainvoke({"line_id": "L1"})
    assert "产线A" in result
    assert "注塑机1" in result


@pytest.mark.asyncio
async def test_get_production_line_not_found(tools: list) -> None:
    tool = _find_tool(tools, "get_production_line")
    result = await tool.ainvoke({"line_id": "L99"})
    assert "未找到" in result


@pytest.mark.asyncio
async def test_list_registered_devices_all(tools: list) -> None:
    tool = _find_tool(tools, "list_registered_devices")
    result = await tool.ainvoke({"line_id": ""})
    assert "注塑机1" in result
    assert "固化炉1" in result


@pytest.mark.asyncio
async def test_list_registered_devices_filtered(tools: list) -> None:
    tool = _find_tool(tools, "list_registered_devices")
    result = await tool.ainvoke({"line_id": "L2"})
    assert "固化炉1" in result
    assert "注塑机1" not in result


@pytest.mark.asyncio
async def test_get_registered_device_found(tools: list) -> None:
    tool = _find_tool(tools, "get_registered_device")
    result = await tool.ainvoke({"device_id": "D1"})
    assert "注塑机1" in result
    assert "injection_molding" in result


@pytest.mark.asyncio
async def test_get_registered_device_not_found(tools: list) -> None:
    tool = _find_tool(tools, "get_registered_device")
    result = await tool.ainvoke({"device_id": "D99"})
    assert "未找到" in result


@pytest.mark.asyncio
async def test_monitor_no_analysis_service(tools: list) -> None:
    tool = _find_tool(tools, "monitor_production_line")
    result = await tool.ainvoke({"line_id": "L1"})
    assert "不可用" in result
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/agent/test_system_tools.py -v
```

Expected: 8 passed

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_system_tools.py
git commit -m "test: add system_tools unit tests"
```

---

### Task 7: Write tests for parameter_tools

**Files:**
- Create: `tests/agent/test_parameter_tools.py`

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations

import pytest

from process_opt.agent.tools.parameter_tools import create_parameter_tools


class MockParameterSet:
    def __init__(self, id: int, name: str, device_type: str, version: int, status: str):
        self.id = id
        self.name = name
        self.device_type = device_type
        self.version = version
        self.status = status
        self.created_by = "test"
        self.note = None
        self.activated_at = None


class MockParameterItem:
    def __init__(self, param_key: str, param_value, unit: str = "", data_type: str = "continuous"):
        self.param_key = param_key
        self.param_value = param_value
        self.unit = unit
        self.data_type = data_type
        self.min_value = None
        self.max_value = None


class MockParameterSetWithItems:
    def __init__(self, parameter_set: MockParameterSet, items: list[MockParameterItem]):
        self.parameter_set = parameter_set
        self.items = items


class MockParameterService:
    def __init__(self) -> None:
        self._sets = [
            MockParameterSet(1, "默认参数", "adhesive_curing", 1, "active"),
            MockParameterSet(2, "优化参数v2", "adhesive_curing", 2, "proposed"),
            MockParameterSet(3, "注塑标准", "injection_molding", 1, "draft"),
        ]
        self._items = {
            1: [MockParameterItem("cure_temp", 145, "°C"), MockParameterItem("cure_time", 45, "min")],
            2: [MockParameterItem("cure_temp", 150, "°C"), MockParameterItem("cure_time", 40, "min")],
            3: [MockParameterItem("melt_temp", 220, "°C")],
        }

    async def list_sets(self) -> list[MockParameterSet]:
        return self._sets

    async def get_set_with_items(self, set_id: int) -> MockParameterSetWithItems | None:
        for s in self._sets:
            if s.id == set_id:
                return MockParameterSetWithItems(s, self._items.get(set_id, []))
        return None

    async def get_latest(self, device_type: str) -> MockParameterSetWithItems | None:
        for s in self._sets:
            if s.device_type == device_type and s.status == "active":
                return MockParameterSetWithItems(s, self._items.get(s.id, []))
        return None

    async def submit(self, set_id: int, actor: str, note: str | None = None) -> MockParameterSet:
        for s in self._sets:
            if s.id == set_id:
                if s.status != "draft":
                    raise ValueError(f"Cannot submit set in status {s.status}")
                s.status = "proposed"
                return s
        raise ValueError(f"Set {set_id} not found")

    async def approve(self, set_id: int, actor: str, note: str | None = None) -> MockParameterSet:
        for s in self._sets:
            if s.id == set_id:
                if s.status != "proposed":
                    raise ValueError(f"Cannot approve set in status {s.status}")
                s.status = "approved"
                return s
        raise ValueError(f"Set {set_id} not found")

    async def reject(self, set_id: int, actor: str, note: str | None = None) -> MockParameterSet:
        for s in self._sets:
            if s.id == set_id:
                if s.status != "proposed":
                    raise ValueError(f"Cannot reject set in status {s.status}")
                s.status = "rejected"
                return s
        raise ValueError(f"Set {set_id} not found")


@pytest.fixture
def tools() -> list:
    return create_parameter_tools(MockParameterService())


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


@pytest.mark.asyncio
async def test_list_parameter_sets_all(tools: list) -> None:
    result = await _find_tool(tools, "list_parameter_sets").ainvoke({"device_type": ""})
    assert "默认参数" in result
    assert "优化参数v2" in result
    assert "注塑标准" in result


@pytest.mark.asyncio
async def test_list_parameter_sets_filtered(tools: list) -> None:
    result = await _find_tool(tools, "list_parameter_sets").ainvoke({"device_type": "adhesive_curing"})
    assert "默认参数" in result
    assert "优化参数v2" in result
    assert "注塑标准" not in result


@pytest.mark.asyncio
async def test_get_parameter_set_found(tools: list) -> None:
    result = await _find_tool(tools, "get_parameter_set").ainvoke({"set_id": 1})
    assert "默认参数" in result
    assert "cure_temp" in result
    assert "145" in result


@pytest.mark.asyncio
async def test_get_parameter_set_not_found(tools: list) -> None:
    result = await _find_tool(tools, "get_parameter_set").ainvoke({"set_id": 99})
    assert "未找到" in result


@pytest.mark.asyncio
async def test_get_latest_active(tools: list) -> None:
    result = await _find_tool(tools, "get_latest_active_parameters").ainvoke({"device_type": "adhesive_curing"})
    assert "默认参数" in result
    assert "cure_temp" in result


@pytest.mark.asyncio
async def test_get_latest_no_active(tools: list) -> None:
    result = await _find_tool(tools, "get_latest_active_parameters").ainvoke({"device_type": "welding"})
    assert "没有激活" in result


@pytest.mark.asyncio
async def test_submit_success(tools: list) -> None:
    result = await _find_tool(tools, "submit_parameter_set").ainvoke({"set_id": 3, "note": "请审批"})
    assert "已提交审批" in result


@pytest.mark.asyncio
async def test_submit_wrong_status(tools: list) -> None:
    result = await _find_tool(tools, "submit_parameter_set").ainvoke({"set_id": 1, "note": ""})
    assert "失败" in result


@pytest.mark.asyncio
async def test_approve_success(tools: list) -> None:
    result = await _find_tool(tools, "approve_parameter_set").ainvoke({"set_id": 2, "note": "同意"})
    assert "已批准" in result


@pytest.mark.asyncio
async def test_reject_success(tools: list) -> None:
    result = await _find_tool(tools, "reject_parameter_set").ainvoke({"set_id": 2, "note": "温度需调整"})
    assert "已驳回" in result
    assert "温度需调整" in result
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/agent/test_parameter_tools.py -v
```

Expected: 10 passed

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_parameter_tools.py
git commit -m "test: add parameter_tools unit tests"
```

---

### Task 8: Write tests for experiment_tools

**Files:**
- Create: `tests/agent/test_experiment_tools.py`

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations

from datetime import datetime

import pytest

from process_opt.agent.tools.experiment_tools import create_experiment_tools


class MockExperimentPlan:
    def __init__(self, id: int, name: str, method: str, status: str = "draft"):
        self.id = id
        self.name = name
        self.process_type = "adhesive_curing"
        self.method = method
        self.status = status
        self.created_by = "test"
        self.created_at = datetime(2026, 6, 1, 10, 0)


class MockExperimentRepo:
    def __init__(self) -> None:
        self._plans = [
            MockExperimentPlan(1, "全因子实验", "full_factorial", "completed"),
            MockExperimentPlan(2, "田口设计", "taguchi", "in_progress"),
            MockExperimentPlan(3, "响应面优化", "central_composite", "draft"),
        ]

    async def list_plans(self, limit: int = 20) -> list[MockExperimentPlan]:
        return self._plans[:limit]


@pytest.fixture
def tools() -> list:
    return create_experiment_tools(MockExperimentRepo())


def _find_tool(tools: list, name: str):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


@pytest.mark.asyncio
async def test_list_experiment_plans_all(tools: list) -> None:
    result = await _find_tool(tools, "list_experiment_plans").ainvoke({"limit": 20})
    assert "全因子实验" in result
    assert "田口设计" in result
    assert "响应面优化" in result
    assert "full_factorial" in result


@pytest.mark.asyncio
async def test_list_experiment_plans_limited(tools: list) -> None:
    result = await _find_tool(tools, "list_experiment_plans").ainvoke({"limit": 1})
    assert "全因子实验" in result
    assert "田口设计" not in result
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/agent/test_experiment_tools.py -v
```

Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_experiment_tools.py
git commit -m "test: add experiment_tools unit tests"
```

---

### Task 9: Integration verification

- [ ] **Step 1: Import check**

```bash
python -c "
from process_opt.agent.tools.system_tools import create_system_tools
from process_opt.agent.tools.parameter_tools import create_parameter_tools
from process_opt.agent.tools.experiment_tools import create_experiment_tools
from process_opt.agent.tools.analysis_tools import create_analysis_tools
print('All imports OK')
"
```

- [ ] **Step 2: Run all agent tests**

```bash
pytest tests/agent/ -v
```

Expected: All 20 new tests + any existing agent tests pass

- [ ] **Step 3: Full test suite**

```bash
pytest -v
```

Expected: No regressions
