"""System-specific agent tools — data access, experiment persistence, tracing.

These tools interact with the system's database repositories and APIs.
Separated from pure-computation analysis tools for clarity.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from process_opt.agent.tools.retry import with_retry
from process_opt.agent.tools.token_utils import truncate_output, estimate_tokens


def create_data_tools(
    repository: Any,
    analysis_service: Any,
    parameter_service: Any | None = None,
    experiment_repo: Any = None,
) -> list:
    """Create data-access tools that interact with system DB/repositories.

    Args:
        repository: DataRepository for querying process/inspection records.
        analysis_service: AnalysisService (for build_dataset).
        parameter_service: Optional ParameterService (for trace_product_full).
        experiment_repo: Optional ExperimentRepository (for save/query experiments).
    """

    @tool
    @with_retry()
    async def query_records(
        device_id: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """查询设备的生产数据记录。返回 barcodes, device_id, 参数值和检测结果。"""
        result = await repository.query_records(
            device_id=device_id or None, page=page, page_size=page_size,
        )
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            return f"未找到设备 `{device_id}` 的生产记录。" if device_id else "当前系统没有生产记录。"

        total_est = 0
        if total > page_size:
            # Estimate total tokens for current page
            est_per_row = estimate_tokens(str(items[0])) if items else 0
            total_est = est_per_row * len(items)

        lines = [
            f"## 生产记录查询",
            f"**设备**: {device_id or '全部'} | **共 {total} 条** | 第 {page} 页",
            "",
            "| 条码 | 设备 | 生产时间 | 参数摘要 | 检测结果 |",
            "|------|------|----------|----------|----------|",
        ]
        for item in items:
            params = item.get("params", {})
            if isinstance(params, dict):
                params_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:3])
            else:
                params_str = str(params)[:60]
            results = item.get("results", {})
            if isinstance(results, dict):
                results_str = ", ".join(f"{k}={v}" for k, v in list(results.items())[:3])
            else:
                results_str = str(results)[:60]
            lines.append(
                f"| {item.get('barcode', '-')} | {item.get('device_id', '-')} | "
                f"{item.get('processed_at', '-')} | {params_str} | {results_str} |"
            )
        result_text = "\n".join(lines)
        result_text, _, _ = truncate_output(result_text, max_tokens=8000)
        return result_text

    @tool
    async def get_devices() -> str:
        """获取系统中所有设备的 ID 列表。"""
        devices = await repository.list_devices()
        if not devices:
            return "当前系统没有注册的设备。"

        lines = [f"## 设备列表 (共 {len(devices)} 台)", ""]
        for d in devices:
            lines.append(f"- `{d}`")
        return "\n".join(lines)

    @tool
    @with_retry()
    async def get_stats() -> str:
        """获取平台统计数据（今日记录数、总记录数、设备数等）。"""
        stats = await repository.get_stats()
        lines = [
            "## 平台统计",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 今日数据量 | {stats.get('today_data_count', 0)} |",
            f"| 总记录数 | {stats.get('total_records', 0)} |",
            f"| 设备数 | {stats.get('device_count', 0)} |",
            f"| 待审批参数集 | {stats.get('pending_approvals', 0)} |",
        ]
        if stats.get("latest_records"):
            lines.append("")
            lines.append("### 最近记录")
            lines.append("| 条码 | 设备 | 时间 |")
            lines.append("|------|------|------|")
            for r in stats["latest_records"]:
                lines.append(f"| {r.get('barcode','-')} | {r.get('device_id','-')} | {r.get('processed_at','-')} |")
        return "\n".join(lines)

    @tool
    async def build_dataset(device_id: str, since: str = "") -> str:
        """从数据库查询设备数据并构建分析数据集。返回 dataset_id 供其他分析工具使用。"""
        from process_opt.analysis.excel import get_dataset
        since_dt: datetime | None = None
        if since:
            since_dt = datetime.fromisoformat(since)
        ds_id = await analysis_service.build_dataset_id(device_id, since=since_dt)
        ds = await get_dataset(ds_id)
        feature_fields = sorted({k for f in ds.features for k in f}) if ds else []
        target_fields = sorted({k for t in ds.targets for k in t}) if ds else []
        sample_count = ds.sample_count if ds else 0
        lines = [
            "## 数据集已构建",
            f"**数据集ID**: `{ds_id}`",
            f"**样本数**: {sample_count}",
            f"**特征字段** ({len(feature_fields)}): {', '.join(feature_fields) if feature_fields else '无'}",
            f"**目标字段** ({len(target_fields)}): {', '.join(target_fields) if target_fields else '无'}",
            "",
            "此 dataset_id 可用于后续分析工具（如 analyze_correlation, run_regression, analyze_importance 等）。",
        ]
        return "\n".join(lines)

    @tool
    async def preview_dataset(dataset_id: str, page: int = 1, size: int = 20) -> str:
        """预览数据集的内容，分页展示数据行和字段统计信息。
        dataset_id: 数据集ID（通过 build_dataset 或文件上传获取）。
        page: 页码（从1开始）。
        size: 每页行数（默认20）。"""
        from process_opt.analysis.excel import get_dataset

        ds = await get_dataset(dataset_id)
        if ds is None:
            return "数据集未找到或已过期，请重新构建数据集。"

        feature_names = sorted({k for f in ds.features for k in f})
        target_names = sorted({k for t in ds.targets for k in t})
        all_columns = feature_names + target_names

        total = ds.sample_count
        start = (page - 1) * size
        end = min(start + size, total)

        lines = [
            "## 数据集预览",
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

        result_text = "\n".join(lines)
        result_text, _, _ = truncate_output(result_text, max_tokens=8000)
        return result_text

    @tool
    @with_retry()
    async def trace_product(barcode: str) -> str:
        """追溯单个产品（barcode）的完整生产链路：工艺参数、检测结果、当前有效参数集。"""
        record = await repository.get_analysis_record(barcode)
        if record is None:
            return f"未找到条码 {barcode} 的生产记录"

        params = record.get("params", {})
        if isinstance(params, str):
            params = json.loads(params)

        inspection = record.get("inspection_result", {})
        if isinstance(inspection, str):
            inspection = json.loads(inspection)

        lines = [
            f"## 产品追溯: {barcode}",
            "",
            f"- **设备**: {record.get('device_id', '-')}",
            f"- **生产时间**: {record.get('processed_at', '-')}",
            "",
            "### 工艺参数",
            "| 参数 | 值 |",
            "|------|----|",
        ]
        for k, v in params.items():
            lines.append(f"| {k} | {v} |")

        lines.append("")
        lines.append("### 检测结果")
        lines.append("| 指标 | 结果 |")
        lines.append("|------|------|")
        if isinstance(inspection, list):
            for item in inspection:
                if isinstance(item, dict):
                    lines.append(f"| {item.get('name', '-')} | {item.get('value', item.get('result', '-'))} |")
        elif isinstance(inspection, dict):
            for k, v in inspection.items():
                lines.append(f"| {k} | {v} |")

        return "\n".join(lines)

    @tool
    async def trace_product_full(barcode: str) -> str:
        """完整追溯单个产品（barcode）的生产链路。返回工艺参数、检测结果、及当前有效参数集对照。
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

    tool_list = [
        query_records, get_devices, get_stats,
        build_dataset, preview_dataset,
        trace_product, trace_product_full,
    ]

    # ---- Conditionally included experiment-persistence tools ----
    if experiment_repo is not None:
        @tool
        async def save_experiment_plan(
            plan_json: str,
        ) -> str:
            """保存实验方案到数据库。plan_json 为实验方案 JSON，包含 name,method,factors,design_runs 等字段。
            返回保存后的实验方案 ID。"""
            from process_opt.experiment.repository import ExperimentPlanCreate

            data = json.loads(plan_json)
            plan = await experiment_repo.create_plan(ExperimentPlanCreate(**data))
            return (
                f"## 实验方案已保存\n\n"
                f"- **方案ID**: {plan.id}\n"
                f"- **名称**: {plan.name}\n"
                f"- **方法**: {plan.method}\n"
                f"- **状态**: {plan.status}\n"
                f"- **运行次数**: {len(plan.design_runs)}"
            )

        @tool
        async def record_experiment_result_for_plan(
            plan_id: int, run_order: int, response_value: float, notes: str = "",
        ) -> str:
            """记录单个实验运行的结果。plan_id 为实验方案ID，run_order 为运行序号，response_value 为响应值。"""
            from process_opt.experiment.repository import ExperimentResultCreate

            await experiment_repo.record_result(plan_id, ExperimentResultCreate(
                run_order=run_order, response_value=response_value, notes=notes or None,
            ))
            return (
                f"## 实验结果已记录\n\n"
                f"- **方案ID**: {plan_id}\n"
                f"- **运行序号**: {run_order}\n"
                f"- **响应值**: {response_value}\n"
                f"- **备注**: {notes or '无'}"
            )

        @tool
        async def get_plan_results(plan_id: int) -> str:
            """获取实验方案的完整结果，包括所有运行记录。plan_id: 实验方案ID。"""
            plan = await experiment_repo.get_plan(plan_id)
            if plan is None:
                return f"未找到实验方案 `{plan_id}`。"
            lines = [
                f"## 实验方案: {plan.name}",
                "",
                f"- **ID**: {plan.id} | **工艺**: {plan.process_type} | **方法**: {plan.method}",
                f"- **状态**: {plan.status} | **创建者**: {plan.created_by}",
                "",
                "### 实验结果",
                "| 运行序号 | 响应值 | 备注 |",
                "|----------|--------|------|",
            ]
            for r in (plan.results or []):
                lines.append(f"| {r.run_order} | {r.response_value} | {r.notes or '-'} |")
            return "\n".join(lines)

        tool_list.extend([save_experiment_plan, record_experiment_result_for_plan, get_plan_results])

    @tool
    async def upload_and_analyze(dataset_id: str) -> str:
        """对上传的数据集自动进行完整分析：数据画像 + 相关性矩阵 + ECharts可视化。
        返回 ECharts 热力图配置，可直接渲染为图表。
        dataset_id 通过上传文件接口获取，或从 build_dataset 获取。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.profiling import profile_dataset
        from process_opt.analysis.correlation import compute_correlation

        ds = await get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found"

        feature_fields = sorted({k for f in ds.features for k in f})
        target_fields = sorted({k for t in ds.targets for k in t})
        all_fields = feature_fields + target_fields

        profile = profile_dataset(ds)
        profile_items = [
            {"field": p.field, "mean": round(p.mean, 3) if p.mean else None,
             "std": round(p.std, 3) if p.std else None, "min": p.min, "max": p.max,
             "missing": p.missing_count, "outlier_count": p.outlier_count}
            for p in profile
        ]

        corr_all = compute_correlation(ds, all_fields, all_fields, "pearson")
        corr_map: dict[tuple[str, str], float] = {}
        for c in corr_all:
            corr_map[(c.field_x, c.field_y)] = round(c.coefficient, 3)
            corr_map[(c.field_y, c.field_x)] = round(c.coefficient, 3)

        heatmap_data: list[list] = []
        labels = all_fields
        for yi, fy in enumerate(labels):
            for xi, fx in enumerate(labels):
                val = corr_map.get((fy, fx), 1.0 if fy == fx else 0.0)
                heatmap_data.append([xi, yi, val])

        corr_text = "\n".join(
            f"| {c[0]} | {c[1]} | {c[2]:.3f} |"
            for c in sorted(
                [[fx, fy, corr_map.get((fx, fy), 0)] for fx in feature_fields for fy in target_fields],
                key=lambda x: abs(x[2]), reverse=True
            )[:15]
        )

        chart = {
            "title": {"text": "相关性矩阵 (Pearson)", "left": "center", "top": 5, "textStyle": {"fontSize": 14}},
            "tooltip": {"position": "top", "formatter": "{b} ↔ {a}: {c}"},
            "grid": {"top": 50, "bottom": 60, "left": 140, "right": 30},
            "xAxis": {"data": labels, "type": "category", "axisLabel": {"rotate": 45, "fontSize": 11}},
            "yAxis": {"data": labels, "type": "category", "axisLabel": {"fontSize": 11}},
            "visualMap": {"min": -1, "max": 1, "calculable": True,
                          "orient": "horizontal", "left": "center", "bottom": "0%",
                          "inRange": {"color": ["#313695", "#4575b4", "#74add1", "#abd9e9", "#fee090", "#fdae61", "#f46d43", "#d73027"]}},
            "series": [{"type": "heatmap", "data": heatmap_data,
                        "label": {"show": True, "fontSize": 10, "formatter": "{c}"},
                        "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}}}]
        }

        echarts_json = json.dumps(chart, ensure_ascii=False)
        return (
            f"## 数据概览\n"
            f"- 样本数: {ds.sample_count}\n"
            f"- 特征字段: {', '.join(feature_fields)}\n"
            f"- 目标字段: {', '.join(target_fields)}\n\n"
            f"## 相关系数表 (特征→目标)\n\n"
            f"| 特征参数 | 目标指标 | 相关系数 |\n|------|------|------|\n{corr_text}\n\n"
            f"## 相关性矩阵热力图\n\n```echarts\n{echarts_json}\n```\n"
        )

    tool_list.append(upload_and_analyze)

    return tool_list
