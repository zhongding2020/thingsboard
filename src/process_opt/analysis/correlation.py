from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, CorrelationResult


def _extract_arrays(
    dataset: AnalysisDataset, feature_fields: list[str], target_fields: list[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n = dataset.sample_count
    if n == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot compute correlation on empty dataset",
        )

    features: dict[str, np.ndarray] = {}
    for field in feature_fields:
        vals = []
        for feat in dataset.features:
            v = feat.get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Field '{field}' contains non-numeric or missing values",
                )
            vals.append(float(v))
        features[field] = np.array(vals, dtype=np.float64)

    targets: dict[str, np.ndarray] = {}
    for field in target_fields:
        vals = []
        for tgt in dataset.targets:
            v = tgt.get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Field '{field}' contains non-numeric or missing values",
                )
            vals.append(float(v))
        targets[field] = np.array(vals, dtype=np.float64)

    return features, targets


def compute_correlation(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_fields: list[str],
    method: str = "pearson",
) -> list[CorrelationResult]:
    features, targets = _extract_arrays(dataset, feature_fields, target_fields)
    results: list[CorrelationResult] = []

    for f_name, f_arr in features.items():
        for t_name, t_arr in targets.items():
            if method == "pearson":
                coeff, p_val = scipy_stats.pearsonr(f_arr, t_arr)
            elif method == "spearman":
                coeff, p_val = scipy_stats.spearmanr(f_arr, t_arr)
            else:
                raise AnalysisError(
                    code="INVALID_CONSTRAINT",
                    message=f"Unknown correlation method: {method}",
                )
            results.append(CorrelationResult(
                field_x=f_name,
                field_y=t_name,
                coefficient=float(coeff),
                p_value=float(p_val),
                method=method,
            ))

    results.sort(key=lambda r: abs(r.coefficient), reverse=True)
    return results
