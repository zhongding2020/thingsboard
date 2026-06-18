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
    experiment_repo: Any = None,
) -> list:
    @tool
    async def query_records(
        device_id: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """查询设备的生产数据记录。返回 barcodes, device_id, 参数值和检测结果。"""
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
        """对设备数据进行统计画像。device_id 可选。"""
        req = AnalysisDatasetRequest(device_id=device_id, page=page, page_size=page_size)
        results = await analysis_service.profile_from_request(req)
        items = [
            {
                "field": r.field, "count": r.count,
                "mean": round(r.mean, 3) if r.mean is not None else None,
                "std": round(r.std, 3) if r.std is not None else None,
                "min": round(r.min, 3) if r.min is not None else None,
                "max": round(r.max, 3) if r.max is not None else None,
                "outlier_count": r.outlier_count,
                "outlier_ratio": round(r.outlier_ratio, 3) if r.outlier_ratio else None,
            }
            for r in results
        ]
        return json.dumps(items, ensure_ascii=False)

    @tool
    async def analyze_correlation(field_x: str, field_y: str, method: str = "pearson") -> str:
        """计算两个参数之间的相关性。method: pearson 或 spearman。"""
        req = CorrelationRequest(field_x=field_x, field_y=field_y, method=method)
        result = await analysis_service.correlation(req)
        return json.dumps({
            "field_x": result.field_x, "field_y": result.field_y,
            "coefficient": round(result.coefficient, 4),
            "p_value": round(result.p_value, 4), "method": result.method,
        }, ensure_ascii=False)

    @tool
    async def analyze_pareto(dataset_id: str, field_y: str) -> str:
        """对数据集进行帕累托分析，找出对 field_y 影响最大的因子排序。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.pareto import compute_pareto
        ds = get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        items = compute_pareto(ds, field_y)
        return json.dumps([i.model_dump() for i in items], ensure_ascii=False)

    @tool
    async def run_regression(
        dataset_id: str, feature_fields: list[str], target_field: str, model_type: str = "linear",
    ) -> str:
        """拟合回归模型。model_type: linear 或 pls。返回 R²、RMSE、系数。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.regression import fit_regression
        ds = get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        result = fit_regression(ds, feature_fields, target_field, model_type)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def recommend_params(
        dataset_id: str, feature_fields: list[str], target_field: str, target_value: float,
    ) -> str:
        """根据历史数据和目标值，推荐最优参数组合。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.recommendation import compute_recommendation
        ds = get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        req = RecommendationRequest(
            dataset_id=dataset_id, feature_fields=feature_fields,
            target_field=target_field, target_value=target_value,
        )
        result = compute_recommendation(ds, feature_fields, req)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def run_spc(device_id: str, field: str = "") -> str:
        """对设备的工艺参数进行 SPC 监控分析。field 可选指定字段。"""
        req = SpcRequest(device_id=device_id, field=field or None)
        result = await analysis_service.spc(req)
        return json.dumps(result.model_dump(), ensure_ascii=False)

    @tool
    async def get_parameters(device_type: str = "") -> str:
        """获取参数集列表。可指定 device_type 过滤。"""
        if parameter_service is None:
            return "Parameter service not available"
        sets = await parameter_service.list_sets()
        if device_type:
            sets = [s for s in sets if getattr(s, "device_type", "") == device_type]
        return json.dumps([s.model_dump() for s in sets], default=str, ensure_ascii=False)

    @tool
    async def get_process_knowledge(process_type: str) -> str:
        """获取指定工艺的参数模板、质量指标、规则约束和分析建议。"""
        template = knowledge_loader.load(process_type)
        if template is None:
            return f"未找到工艺 '{process_type}' 的知识模板"
        return knowledge_loader.build_system_prompt(template)

    @tool
    async def build_dataset(device_id: str, since: str = "") -> str:
        """从数据库查询设备数据并构建分析数据集。返回 dataset_id 供其他分析工具使用。"""
        from process_opt.analysis.excel import get_dataset
        since_dt: datetime | None = None
        if since:
            since_dt = datetime.fromisoformat(since)
        ds_id = await analysis_service._builder.build_to_dataset_id(device_id, since=since_dt)
        ds = get_dataset(ds_id)
        feature_fields = sorted({k for f in ds.features for k in f}) if ds else []
        target_fields = sorted({k for t in ds.targets for k in t}) if ds else []
        return json.dumps({
            "dataset_id": ds_id,
            "fields": {"features": feature_fields, "targets": target_fields},
            "sample_count": ds.sample_count if ds else 0,
        }, ensure_ascii=False)

    @tool
    async def design_experiment(factors_json: str, method: str = "full_factorial", center_points: int = 0) -> str:
        """生成 DOE 实验设计方案。factors_json 为因子列表 JSON，格式 [{"name":"温度","low":100,"high":150,"unit":"°C"},...]。
        method 可选: full_factorial, frac_factorial, central_composite, box_behnken, taguchi。
        返回实验设计矩阵。"""
        from process_opt.analysis.doe_schemas import DOEConfig, DesignMethod
        from process_opt.analysis.doe_service import generate_design

        factors = json.loads(factors_json)
        config = DOEConfig(
            method=DesignMethod(method),
            factors=factors,
            center_points=center_points,
        )
        design = generate_design(config)
        result = {
            "method": design.method.value,
            "run_count": design.run_count,
            "runs": [{"run": r.run_order, "factors": r.factor_values} for r in design.runs],
        }
        return json.dumps(result, ensure_ascii=False)

    @tool
    async def analyze_experiment(
        factors_json: str, run_results_json: str, response_name: str = "response",
    ) -> str:
        """对实验结果进行 ANOVA 方差分析。factors_json 为因子列表（同 design_experiment），
        run_results_json 为实验结果列表 [{"run_order":1,"response":85.2},...]。
        返回各因子的效应、系数、p值和显著性。"""
        from process_opt.analysis.doe_schemas import ANOVARequest, ExperimentResult, Factor
        from process_opt.analysis.doe_service import run_anova

        factors = [Factor(**f) for f in json.loads(factors_json)]
        results_data = json.loads(run_results_json)
        results = [ExperimentResult(**r) for r in results_data]

        n_runs = len(results)
        design_runs: list[Any] = []
        for i in range(n_runs):
            d = {}
            half = len(factors) // 2
            for j, f in enumerate(factors):
                d[f.name] = f.low if (i & (1 << j)) == 0 else f.high
            from process_opt.analysis.doe_schemas import DOERun
            design_runs.append(DOERun(run_order=i+1, standard_order=i+1, factor_values=d))

        req = ANOVARequest(
            factors=factors, design_runs=design_runs, results=results,
            response_name=response_name,
        )
        anova = run_anova(req)
        return json.dumps({
            "response": anova.response_name,
            "r_squared": anova.r_squared,
            "adj_r_squared": anova.adj_r_squared,
            "model_significant": anova.model_significant,
            "effects": [{
                "factor": e.factor,
                "effect": e.effect,
                "coefficient": e.coefficient,
                "p_value": e.p_value,
                "significant": e.significant,
            } for e in anova.effects if e.factor != "intercept"],
            "summary": anova.summary,
        }, ensure_ascii=False)

    tool_list = [
        query_records, get_devices, get_stats, profile_data,
        analyze_correlation, analyze_pareto, run_regression,
        recommend_params, run_spc, get_parameters,
        get_process_knowledge, build_dataset,
        design_experiment, analyze_experiment,
    ]

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
            return json.dumps({"plan_id": plan.id, "name": plan.name, "status": plan.status}, ensure_ascii=False)

        @tool
        async def record_experiment_result_for_plan(
            plan_id: int, run_order: int, response_value: float, notes: str = "",
        ) -> str:
            """记录单个实验运行的结果。plan_id 为实验方案ID，run_order 为运行序号，response_value 为响应值。"""
            from process_opt.experiment.repository import ExperimentResultCreate

            await experiment_repo.record_result(plan_id, ExperimentResultCreate(
                run_order=run_order, response_value=response_value, notes=notes or None,
            ))
            return json.dumps({"status": "recorded", "plan_id": plan_id, "run_order": run_order}, ensure_ascii=False)

        @tool
        async def get_experiment_results(plan_id: int) -> str:
            """获取实验方案的完整结果，包括所有运行记录。"""
            plan = await experiment_repo.get_plan(plan_id)
            if plan is None:
                return "Experiment plan not found"
            return json.dumps(plan.model_dump(), default=str, ensure_ascii=False)

        tool_list.extend([save_experiment_plan, record_experiment_result_for_plan, get_experiment_results])

    @tool
    async def trace_product(barcode: str) -> str:
        """追溯单个产品（barcode）的完整生产链路：工艺参数、检测结果、当前有效参数集。"""
        record = await repository.get_analysis_record(barcode)
        if record is None:
            return f"未找到条码 {barcode} 的生产记录"

        params = record.get("params", {})
        if isinstance(params, str):
            params = json.loads(params)

        return json.dumps({
            "barcode": barcode,
            "device_id": record.get("device_id", ""),
            "product_model": record.get("product_model", ""),
            "process_params": params,
            "inspection_result": record.get("inspection_result", {}),
            "processed_at": str(record.get("processed_at", "")),
        }, default=str, ensure_ascii=False)

    tool_list.append(trace_product)

    @tool
    async def generate_report(
        title: str, sections_json: str, metadata_json: str = "{}",
    ) -> str:
        """生成工艺分析 Markdown 报告。title 报告标题，sections_json 为章节列表 JSON，
        每章含 title 和 content。metadata_json 可包含设备ID、工艺类型等元信息。"""
        from process_opt.analysis.report import generate_markdown_report

        sections = json.loads(sections_json)
        metadata = json.loads(metadata_json) if metadata_json else None
        report = generate_markdown_report(title=title, sections=sections, metadata=metadata)
        return report

    tool_list.append(generate_report)

    @tool
    async def upload_and_analyze(dataset_id: str) -> str:
        """对上传的数据集自动进行完整分析：数据画像 + 相关性矩阵 + ECharts可视化。
        返回 ECharts 热力图配置，可直接渲染为图表。
        dataset_id 通过上传文件接口获取，或从 build_dataset 获取。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.profiling import profile_dataset
        from process_opt.analysis.correlation import compute_correlation

        ds = get_dataset(dataset_id)
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
