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
        """获取参数集列表。"""
        if parameter_service is None:
            return "Parameter service not available"
        sets = await parameter_service.list_sets()
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

    return [
        query_records, get_devices, get_stats, profile_data,
        analyze_correlation, analyze_pareto, run_regression,
        recommend_params, run_spc, get_parameters,
        get_process_knowledge, build_dataset,
    ]
