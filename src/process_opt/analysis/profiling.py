from __future__ import annotations

import numpy as np

from process_opt.analysis.schemas import AnalysisDataset, ProfilingResult


def _collect_values(dataset: AnalysisDataset) -> dict[str, list[float | None]]:
    values: dict[str, list[float | None]] = {}
    for feat in dataset.features:
        for key, val in feat.items():
            values.setdefault(key, []).append(val)
    for tgt in dataset.targets:
        for key, val in tgt.items():
            values.setdefault(key, []).append(val)
    return values


def profile_dataset(dataset: AnalysisDataset) -> list[ProfilingResult]:
    collected = _collect_values(dataset)
    results: list[ProfilingResult] = []

    for field, vals in collected.items():
        total = len(vals)
        missing = sum(1 for v in vals if v is None)
        numeric = [v for v in vals if isinstance(v, (int, float))]

        if not numeric:
            results.append(ProfilingResult(
                field=field,
                count=total,
                missing_count=missing,
                missing_rate=missing / total if total > 0 else 0.0,
            ))
            continue

        arr = np.array(numeric, dtype=np.float64)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = int(np.sum((arr < lower) | (arr > upper)))

        results.append(ProfilingResult(
            field=field,
            count=total,
            missing_count=missing,
            missing_rate=missing / total if total > 0 else 0.0,
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            iqr_outliers=outliers,
        ))

    return results
