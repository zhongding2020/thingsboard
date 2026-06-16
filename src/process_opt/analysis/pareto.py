from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, ParetoItem


def _classify_strength(r: float) -> str:
    abs_r = abs(r)
    if abs_r > 0.7:
        return "strong"
    if abs_r > 0.5:
        return "medium"
    if abs_r > 0.3:
        return "weak"
    return "negligible"


def compute_pareto(
    dataset: AnalysisDataset,
    field_y: str,
) -> list[ParetoItem]:
    if dataset.sample_count == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot compute Pareto on empty dataset",
        )

    y_vals = []
    for tgt in dataset.targets:
        v = tgt.get(field_y)
        if v is None or not isinstance(v, (int, float)):
            raise AnalysisError(
                code="NON_NUMERIC_FIELD",
                message=f"Target field '{field_y}' contains non-numeric or missing values",
            )
        y_vals.append(float(v))
    y_arr = np.array(y_vals, dtype=np.float64)

    feature_names = sorted({k for f in dataset.features for k in f})

    pairs: list[tuple[str, float]] = []
    for field in feature_names:
        x_vals = []
        for feat in dataset.features:
            v = feat.get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Feature field '{field}' contains non-numeric or missing values",
                )
            x_vals.append(float(v))
        x_arr = np.array(x_vals, dtype=np.float64)
        coeff, _ = scipy_stats.pearsonr(x_arr, y_arr)
        pairs.append((field, abs(float(coeff))))

    pairs.sort(key=lambda p: p[1], reverse=True)
    total = sum(p[1] for p in pairs) or 1.0

    items: list[ParetoItem] = []
    cumulative = 0.0
    for field, abs_r in pairs:
        contribution = (abs_r / total) * 100.0
        cumulative += contribution
        items.append(ParetoItem(
            field=field,
            coefficient=round(abs_r, 4),
            contribution_pct=round(contribution, 2),
            cumulative_pct=round(cumulative, 2),
            strength=_classify_strength(abs_r),
        ))

    return items
