"""Pure-computation analysis tools — statistics, DOE, optimization, reporting.

These tools perform mathematical analysis without direct database access.
Data-access tools (query, trace, build dataset, save experiments) live in data_tools.py.
"""

from __future__ import annotations

import json
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

from process_opt.agent.tools.retry import with_retry


def create_analysis_tools(
    repository: Any,
    analysis_service: Any,
    parameter_service: Any | None,
    knowledge_loader: KnowledgeLoader,
    experiment_repo: Any = None,
) -> list:
    """Create pure-computation analysis tools.

    These tools perform statistical analysis, DOE generation, optimization,
    and report generation. They do NOT directly query databases — use data_tools
    for that.
    """

    @tool
    async def profile_data(device_id: str = "", page: int = 1, page_size: int = 50) -> str:
        """对设备数据进行统计画像。device_id 可选。"""
        req = AnalysisDatasetRequest(device_id=device_id, page=page, page_size=page_size)
        results = await analysis_service.profile_from_request(req)
        lines = ["## 数据画像", f"**设备**: {device_id or '全部'} | **字段数**: {len(results)}", ""]
        lines.append("| 字段 | 样本数 | 均值 | 标准差 | 最小值 | 最大值 | 异常值 |")
        lines.append("|------|--------|------|--------|--------|--------|--------|")
        for r in results:
            mean_str = f"{r.mean:.4f}" if r.mean is not None else "N/A"
            std_str = f"{r.std:.4f}" if r.std is not None else "N/A"
            min_str = f"{r.min:.4f}" if r.min is not None else "N/A"
            max_str = f"{r.max:.4f}" if r.max is not None else "N/A"
            lines.append(f"| {r.field} | {r.count} | {mean_str} | {std_str} | {min_str} | {max_str} | {r.iqr_outliers} |")
        return "\n".join(lines)

    @tool
    @with_retry()
    async def analyze_correlation(field_x: str, field_y: str, method: str = "pearson") -> str:
        """计算两个参数之间的相关性。method: pearson 或 spearman。"""
        req = CorrelationRequest(field_x=field_x, field_y=field_y, method=method)
        result = await analysis_service.correlation(req)
        coeff = result.coefficient
        abs_coeff = abs(coeff)
        if abs_coeff > 0.7:
            strength = "强相关"
        elif abs_coeff > 0.4:
            strength = "中等相关"
        else:
            strength = "弱相关"
        lines = [
            f"## 相关性分析: {field_x} vs {field_y}",
            f"**方法**: {method} | **相关系数**: {coeff:.4f} | **p值**: {result.p_value:.4f}",
            f"**解释**: {strength}",
        ]
        return "\n".join(lines)

    @tool
    async def analyze_pareto(dataset_id: str, field_y: str) -> str:
        """对数据集进行帕累托分析，找出对 field_y 影响最大的因子排序。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.pareto import compute_pareto
        ds = await get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        items = compute_pareto(ds, field_y)
        lines = [f"## 帕累托分析: {field_y}", ""]
        lines.append("| 因子 | 相关系数 | 贡献% | 累计% | 强度 |")
        lines.append("|------|----------|-------|-------|------|")
        for item in items[:10]:
            lines.append(f"| {item.field} | {item.coefficient:.4f} | {item.contribution_pct:.1f}% | {item.cumulative_pct:.1f}% | {item.strength} |")
        return "\n".join(lines)

    @tool
    @with_retry()
    async def run_regression(
        dataset_id: str, feature_fields: list[str], target_field: str, model_type: str = "linear",
    ) -> str:
        """拟合回归模型。model_type: linear 或 pls。返回 R²、RMSE、系数。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.regression import fit_regression
        ds = await get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        result = fit_regression(ds, feature_fields, target_field, model_type)
        lines = [
            "## 回归分析",
            f"**目标**: {target_field} | **R²**: {result.r_squared:.4f} | **RMSE**: {result.rmse:.4f}",
            f"**模型**: {result.model_type}",
            "",
            "### 系数",
            "| 特征 | 系数 |",
            "|------|------|",
        ]
        for field, value in result.coefficients.items():
            lines.append(f"| {field} | {value:.6f} |")
        return "\n".join(lines)

    @tool
    @with_retry()
    async def recommend_params(
        dataset_id: str, feature_fields: list[str], target_field: str, target_value: float,
    ) -> str:
        """根据历史数据和目标值，推荐最优参数组合。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.recommendation import compute_recommendation
        ds = await get_dataset(dataset_id)
        if ds is None:
            return "Dataset not found or expired"
        req = RecommendationRequest(
            dataset_id=dataset_id, feature_fields=feature_fields,
            target_field=target_field, target_value=target_value,
        )
        result = compute_recommendation(ds, feature_fields, req)

        rule_violations: list[str] = []
        try:
            from process_opt.knowledge.rules import RuleEngine

            engine = RuleEngine()
            params_to_check = {k: v for k, v in result.recommended_parameters.items()}
            for proc in knowledge_loader.list_processes():
                template = knowledge_loader.load(proc["process_type"])
                if template is None:
                    continue
                checks = engine.check_params(template, params_to_check)
                for c in checks:
                    if not c.triggered:
                        continue
                    if c.rule.type == "hard_constraint":
                        rule_violations.append(f"❌ [{proc['display_name']}] {c.violation}")
                    else:
                        rule_violations.append(f"⚠ [{proc['display_name']}] {c.violation}")
        except Exception:
            pass

        parts = [
            "## 参数推荐结果",
            f"**模型 R²**: {result.model_metrics.get('r_squared', 0):.4f}",
            f"**RMSE**: {result.model_metrics.get('rmse', 0):.4f}",
            f"**目标值**: {target_value} | **预测值**: {result.predicted_target:.2f}",
            "",
            "### 推荐参数",
            "| 参数 | 推荐值 |",
            "|------|--------|",
        ]
        for k, v in result.recommended_parameters.items():
            parts.append(f"| {k} | {v:.2f} |")

        if result.alternatives:
            parts.append("")
            parts.append("### 备选方案")
            parts.append("| # | 参数组合 |")
            parts.append("|---|----------|")
            for i, alt in enumerate(result.alternatives[:5]):
                params_str = ", ".join(f"{k}={v:.2f}" for k, v in alt.items())
                parts.append(f"| {i + 1} | {params_str} |")

        if result.risk_notes:
            parts.append("")
            parts.append("### 风险提示")
            for note in result.risk_notes:
                parts.append(f"- {note}")

        if rule_violations:
            parts.append("")
            parts.append("### 规则校验")
            parts.extend(rule_violations)
        else:
            parts.append("")
            parts.append("✅ 所有推荐参数符合已知工艺规则。")

        return "\n".join(parts)

    @tool
    @with_retry()
    async def run_spc(device_id: str, field: str = "") -> str:
        """对设备的工艺参数进行 SPC 监控分析。field 可选指定字段。"""
        try:
            req = SpcRequest(device_id=device_id, field=field or None)
            result = await analysis_service.spc(req)
        except Exception as e:
            msg = str(e)
            if "No samples" in msg or "INSUFFICIENT" in msg:
                return (
                    f"## SPC 监控: {field or '全部字段'}\n\n"
                    f"设备 `{device_id}` 暂无生产数据，无法执行 SPC 分析。\n\n"
                    f"建议：先通过数据接入网关上报工艺参数，或使用 `process-opt-mock` 生成模拟数据。"
                )
            return f"SPC 分析失败: {msg}"

        lines = [f"## SPC 监控: {field or '全部字段'}", ""]
        if result.overview:
            lines.append("| 字段 | 均值 | 标准差 | USL | LSL | Cpk | 异常值 | 状态 |")
            lines.append("|------|------|--------|-----|-----|-----|--------|------|")
            for p in result.overview:
                cpk_str = f"{p.cpk:.4f}" if p.cpk is not None else "N/A"
                lines.append(f"| {p.field} | {p.mean:.4f} | {p.std:.4f} | {p.usl} | {p.lsl} | {cpk_str} | {p.outlier_count} | {p.status} |")
        if result.capability:
            cap = result.capability
            lines.append("")
            lines.append(f"**过程能力**: Cp={cap.cp:.4f} | Cpk={cap.cpk:.4f} | Pp={cap.pp:.4f} | Ppk={cap.ppk:.4f}")
        if result.summary:
            lines.append("")
            lines.append(f"**数据统计**: 样本数={result.summary.n} | 均值={result.summary.mean:.4f} | 标准差={result.summary.std:.4f}")
        if result.i_chart or result.mr_chart:
            chart_data: dict = {}
            if result.i_chart:
                chart_data["i_chart"] = result.i_chart.model_dump()
            if result.mr_chart:
                chart_data["mr_chart"] = result.mr_chart.model_dump()
            lines.append("")
            lines.append(f"```echarts\n{json.dumps(chart_data, ensure_ascii=False)}\n```")
        if result.histogram:
            lines.append("")
            lines.append(f"```echarts\n{json.dumps(result.histogram.model_dump(), ensure_ascii=False)}\n```")
        return "\n".join(lines)

    @tool
    async def get_process_knowledge(process_type: str) -> str:
        """获取指定工艺的参数模板、质量指标、规则约束和分析建议。"""
        template = knowledge_loader.load(process_type)
        if template is None:
            return f"未找到工艺 '{process_type}' 的知识模板"
        lines = [f"## 工艺知识: {template.display_name}", ""]
        if template.description:
            lines.append(f"{template.description}")
            lines.append("")
        if template.parameters:
            lines.append("### 工艺参数")
            lines.append("| 参数 | 单位 | 范围 | 目标 | 重要性 |")
            lines.append("|------|------|------|------|--------|")
            for p in template.parameters:
                lo = p.range.min
                hi = p.range.max
                t_lo = p.target.min
                t_hi = p.target.max
                lines.append(f"| {p.name}({p.key}) | {p.unit} | {lo}-{hi} | {t_lo}-{t_hi} | {p.importance.value} |")
        if template.quality_metrics:
            lines.append("")
            lines.append("### 质量指标")
            lines.append("| 指标 | 单位 | USL | LSL |")
            lines.append("|------|------|-----|-----|")
            for m in template.quality_metrics:
                usl_str = f"{m.usl}" if m.usl is not None else "N/A"
                lsl_str = f"{m.lsl}" if m.lsl is not None else "N/A"
                lines.append(f"| {m.name}({m.key}) | {m.unit} | {usl_str} | {lsl_str} |")
        return "\n".join(lines)

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
        factor_names = [f.name for f in design.factors]
        lines = [
            f"## DOE 实验设计: {design.method.value}",
            f"**因素数**: {len(design.factors)} | **实验次数**: {design.run_count}",
            "",
        ]
        header = "| 运行 | " + " | ".join(factor_names) + " |"
        sep = "|------|" + "|".join(["------"] * len(factor_names)) + "|"
        lines.append(header)
        lines.append(sep)
        for run in design.runs:
            vals = " | ".join(f"{run.factor_values.get(name, 0):.2f}" for name in factor_names)
            lines.append(f"| {run.run_order} | {vals} |")
        return "\n".join(lines)

    @tool
    async def analyze_experiment(
        factors_json: str = "", run_results_json: str = "", response_name: str = "response",
        plan_id: int = 0,
    ) -> str:
        """对实验结果进行 ANOVA 方差分析。可传入 plan_id 使用已保存的实验方案，
        或传入 factors_json 和 run_results_json 进行即时分析。
        返回各因子的效应、系数、p值和显著性。"""
        from process_opt.analysis.doe_schemas import ANOVARequest, ExperimentResult, Factor, DOERun
        from process_opt.analysis.doe_service import run_anova

        if plan_id > 0 and experiment_repo is not None:
            plan = await experiment_repo.get_plan(plan_id)
            if plan is None:
                return f"Experiment plan {plan_id} not found"
            factors = [Factor(**f) if isinstance(f, dict) else f for f in plan.factors]
            design_runs = [DOERun(
                run_order=r.get("run_order", i + 1),
                standard_order=r.get("standard_order", r.get("run_order", i + 1)),
                factor_values=r.get("factor_values", {}),
            ) for i, r in enumerate(plan.design_runs)]
            results = [ExperimentResult(
                run_order=r.run_order, response=r.response_value or 0.0,
            ) for r in (plan.results or [])]
            response_name = plan.response_name or response_name
        else:
            factors = [Factor(**f) for f in json.loads(factors_json)]
            results_data = json.loads(run_results_json)
            results = [ExperimentResult(**r) for r in results_data]

            n_runs = len(results)
            design_runs: list[Any] = []
            for i in range(n_runs):
                d = {}
                for j, f in enumerate(factors):
                    d[f.name] = f.low if (i & (1 << j)) == 0 else f.high
                design_runs.append(DOERun(run_order=i+1, standard_order=i+1, factor_values=d))

        req = ANOVARequest(
            factors=factors, design_runs=design_runs, results=results,
            response_name=response_name,
        )
        anova = run_anova(req)
        lines = [
            f"## ANOVA 分析: {anova.response_name}",
            f"**R²**: {anova.r_squared:.4f} | **Adj R²**: {anova.adj_r_squared:.4f}",
            f"**模型显著性**: {'是' if anova.model_significant else '否'}",
            f"**{anova.summary}**",
            "",
            "| 因子 | 效应 | 系数 | p值 | 显著 |",
            "|------|------|------|------|------|",
        ]
        for e in anova.effects:
            if e.factor == "intercept":
                continue
            p_str = f"{e.p_value:.4f}" if e.p_value >= 0.0001 else "<0.0001"
            sig = "✓" if e.significant else ""
            lines.append(f"| {e.factor} | {e.effect:.4f} | {e.coefficient:.4f} | {p_str} | {sig} |")
        return "\n".join(lines)

    @tool
    async def analyze_importance(dataset_id: str, target_field: str) -> str:
        """分析各特征参数对目标质量指标的重要性排序。使用随机森林模型计算特征重要性。
        dataset_id: 数据集ID（通过 build_dataset 获取）。
        target_field: 目标质量指标字段名。"""
        from process_opt.analysis.excel import get_dataset
        from process_opt.analysis.importance import compute_importance

        ds = await get_dataset(dataset_id)
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

        ds = await get_dataset(dataset_id)
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

    return [
        profile_data,
        analyze_correlation, analyze_pareto, run_regression,
        recommend_params, run_spc,
        get_process_knowledge,
        design_experiment, analyze_experiment,
        analyze_importance, optimize_parameters,
        generate_report,
    ]
