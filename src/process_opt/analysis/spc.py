from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats

from process_opt.analysis.schemas import (
    AnalysisDataset,
    Capability,
    Histogram,
    IChart,
    MrChart,
    PChart,
    ParamOverview,
    SpcResult,
    SummaryStats,
)


def compute_imr(values: list[float], labels: list[str]) -> tuple[IChart, MrChart]:
    """Compute I individual chart and MR moving range chart.
    
    I chart: CL=mean, UCL=mean+3σ, LCL=mean-3σ
    MR chart: CL=MR̄, UCL=3.267*MR̄ (D4 for n=2)
    """
    arr = np.array(values, dtype=np.float64)
    n = len(arr)
    mean = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    ucl = mean + 3 * sigma
    lcl = mean - 3 * sigma

    mr_vals = [abs(arr[i] - arr[i - 1]) for i in range(1, n)]
    mr_bar = float(np.mean(mr_vals)) if mr_vals else 0.0
    ucl_mr = 3.267 * mr_bar

    alerts = [i for i, v in enumerate(arr) if v > ucl or v < lcl]

    return (
        IChart(values=values, labels=labels, mean=mean, ucl=ucl, lcl=lcl, alerts=alerts),
        MrChart(values=mr_vals, labels=labels[1:], mr_bar=mr_bar, ucl=ucl_mr),
    )


def compute_histogram(values: list[float], usl: float, lsl: float, bin_count: int = 20) -> Histogram:
    """Compute histogram bins and normal curve fit."""
    arr = np.array(values, dtype=np.float64)
    counts, edges = np.histogram(arr, bins=bin_count)
    bins = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]

    mu = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    x_range = np.linspace(lsl - sigma, usl + sigma, 200)
    curve = sp_stats.norm.pdf(x_range, mu, sigma) * len(arr) * (edges[1] - edges[0])

    return Histogram(
        bins=bins,
        counts=counts.tolist(),
        curve_x=x_range.tolist(),
        curve_y=curve.tolist(),
    )


def compute_capability(values: list[float], usl: float, lsl: float, target: float | None = None) -> Capability:
    """Compute process capability indices Cp, Cpk, Pp, Ppk."""
    arr = np.array(values, dtype=np.float64)
    mean = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    sigma_p = float(np.std(arr, ddof=0))

    cp = (usl - lsl) / (6 * sigma) if sigma > 0 else 0.0
    cpk = min((usl - mean) / (3 * sigma), (mean - lsl) / (3 * sigma)) if sigma > 0 else 0.0
    pp = (usl - lsl) / (6 * sigma_p) if sigma_p > 0 else 0.0
    ppk = min((usl - mean) / (3 * sigma_p), (mean - lsl) / (3 * sigma_p)) if sigma_p > 0 else 0.0

    return Capability(cp=cp, cpk=cpk, pp=pp, ppk=ppk, usl=usl, lsl=lsl, target=target)


def compute_p_chart(results: list[str], time_groups: list[str]) -> PChart:
    """Compute p-chart for defect rate over time periods."""
    from collections import Counter
    periods = sorted(set(time_groups))
    defect_rates: list[float] = []
    total_defects = 0
    total_count = 0
    for p in periods:
        indices = [i for i, tp in enumerate(time_groups) if tp == p]
        group_results = [results[i] for i in indices]
        n = len(group_results)
        defects = sum(1 for r in group_results if r == "fail")
        total_defects += defects
        total_count += n
        defect_rates.append(defects / n if n > 0 else 0.0)

    p_bar = total_defects / total_count if total_count > 0 else 0.0
    ucl_p = p_bar + 3 * np.sqrt(p_bar * (1 - p_bar) / (total_count / len(periods))) if total_count > 0 and len(periods) > 0 else 0.0

    return PChart(
        periods=periods,
        rates=[round(r, 4) for r in defect_rates],
        total_count=total_count,
        defect_count=total_defects,
        ucl=round(ucl_p, 4),
        p_bar=round(p_bar, 4),
    )


def compute_summary(values: list[float]) -> SummaryStats:
    """Compute summary statistics with normality test."""
    arr = np.array(values, dtype=np.float64)
    _, p_val = sp_stats.normaltest(arr) if len(arr) >= 8 else (None, None)
    return SummaryStats(
        n=len(arr),
        mean=float(np.mean(arr)),
        std=float(np.std(arr, ddof=1)),
        min_val=float(np.min(arr)),
        max_val=float(np.max(arr)),
        normality_p=float(p_val) if p_val is not None else None,
    )


def _determine_status(cpk: float | None) -> str:
    """Cpk >= 1.33 normal, 1.0 <= Cpk < 1.33 marginal, Cpk < 1.0 abnormal. None -> no spec limits."""
    if cpk is None:
        return "no_spec"
    if cpk >= 1.33:
        return "normal"
    if cpk >= 1.0:
        return "marginal"
    return "abnormal"


def compute_overview(dataset: AnalysisDataset, spec: dict[str, dict[str, float]] | None = None) -> list[ParamOverview]:
    """Compute SPC overview for all parameter fields in the dataset.
    
    spec: optional dict of field -> {usl, lsl, target}. When absent, Cpk is null.
    """
    field_values: dict[str, list[float]] = {}
    for feat in dataset.features:
        for key, val in feat.items():
            if isinstance(val, (int, float)):
                field_values.setdefault(key, []).append(float(val))
    for tgt in dataset.targets:
        for key, val in tgt.items():
            if isinstance(val, (int, float)):
                field_values.setdefault(key, []).append(float(val))

    overviews = []
    for field, vals in field_values.items():
        arr = np.array(vals, dtype=np.float64)
        mean = float(np.mean(arr))
        sigma = float(np.std(arr, ddof=1))
        usl = mean + 3 * sigma
        lsl = mean - 3 * sigma

        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = int(np.sum((arr < lower_bound) | (arr > upper_bound)))

        field_spec = (spec or {}).get(field)
        cpk: float | None = None
        if field_spec and field_spec.get("usl") is not None and field_spec.get("lsl") is not None and sigma > 0:
            u = field_spec["usl"]
            ll = field_spec["lsl"]
            cpk = min((u - mean) / (3 * sigma), (mean - ll) / (3 * sigma))

        overviews.append(ParamOverview(
            field=field,
            n=len(vals),
            mean=round(mean, 2),
            std=round(sigma, 2),
            usl=round(usl, 2) if field_spec is None or field_spec.get("usl") is None else field_spec["usl"],
            lsl=round(lsl, 2) if field_spec is None or field_spec.get("lsl") is None else field_spec["lsl"],
            cpk=round(cpk, 2) if cpk is not None else None,
            outlier_count=outliers,
            status=_determine_status(cpk),
        ))

    overviews.sort(key=lambda o: o.field)
    return overviews


def build_spc_result(
    overview_dataset: AnalysisDataset,
    field_dataset: AnalysisDataset,
    field: str | None,
    usl: float | None,
    lsl: float | None,
    target: float | None,
) -> SpcResult:
    """Build complete SPC result. overview_dataset used for overview (all fields), field_dataset for charts (one field)."""
    spec = None
    if usl is not None and lsl is not None and field is not None:
        spec = {field: {"usl": usl, "lsl": lsl, "target": target}}
    overview = compute_overview(overview_dataset, spec=spec)

    if field is None:
        return SpcResult(overview=overview)

    feature_values: list[float] = []
    result_values: list[str] = []
    labels: list[str] = []
    for i in range(field_dataset.sample_count):
        feat = field_dataset.features[i]
        tgt = field_dataset.targets[i]
        val = feat.get(field)
        if not isinstance(val, (int, float)):
            val = tgt.get(field)
        if isinstance(val, (int, float)):
            feature_values.append(float(val))
            labels.append(field_dataset.metadata[i].get("barcode", str(i)) if field_dataset.metadata else str(i))
        for k, v in tgt.items():
            if isinstance(v, str):
                result_values.append(v)

    if not feature_values:
        return SpcResult(overview=overview)

    arr = np.array(feature_values, dtype=np.float64)

    has_spec = usl is not None and lsl is not None
    final_usl = usl if has_spec else float(np.mean(arr) + 3 * np.std(arr, ddof=1))
    final_lsl = lsl if has_spec else float(np.mean(arr) - 3 * np.std(arr, ddof=1))
    final_target = target

    i_chart, mr_chart = compute_imr(feature_values, labels)
    histogram = compute_histogram(feature_values, final_usl, final_lsl)
    capability = compute_capability(feature_values, final_usl, final_lsl, final_target) if has_spec else None
    
    if result_values:
        processed_dates = [m.get("processed_at", "")[:10] for m in field_dataset.metadata if m]
        field_indices = [i for i in range(field_dataset.sample_count) if isinstance(field_dataset.features[i].get(field), (int, float))]
        matching_results = [result_values[i] for i in range(len(field_indices)) if i < len(result_values)]
        matching_dates = [processed_dates[i] for i in range(len(field_indices)) if i < len(processed_dates)]
        p_chart = compute_p_chart(matching_results if matching_results else result_values,
                                   matching_dates if matching_dates else [""])
    else:
        p_chart = PChart(periods=[], rates=[], total_count=0, defect_count=0, ucl=0.0, p_bar=0.0)
    
    summary = compute_summary(feature_values)

    return SpcResult(
        overview=overview,
        i_chart=i_chart,
        mr_chart=mr_chart,
        histogram=histogram,
        capability=capability,
        p_chart=p_chart,
        summary=summary,
    )
