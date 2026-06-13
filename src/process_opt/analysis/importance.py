from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, ImportanceResult


def _extract_arrays(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
) -> tuple[np.ndarray, np.ndarray]:
    n = dataset.sample_count
    if n == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot compute importance on empty dataset",
        )

    feat_cols: list[list[float]] = [[] for _ in feature_fields]
    tgt_vals: list[float] = []

    for i in range(n):
        for j, field in enumerate(feature_fields):
            v = dataset.features[i].get(field)
            if v is None or not isinstance(v, (int, float)):
                raise AnalysisError(
                    code="NON_NUMERIC_FIELD",
                    message=f"Field '{field}' contains non-numeric or missing values",
                )
            feat_cols[j].append(float(v))
        v = dataset.targets[i].get(target_field)
        if v is None or not isinstance(v, (int, float)):
            raise AnalysisError(
                code="NON_NUMERIC_FIELD",
                message=f"Target field '{target_field}' contains non-numeric or missing values",
            )
        tgt_vals.append(float(v))

    X = np.column_stack([np.array(col, dtype=np.float64) for col in feat_cols])
    y = np.array(tgt_vals, dtype=np.float64)
    return X, y


def compute_importance(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
    method: str = "random_forest",
) -> ImportanceResult:
    X, y = _extract_arrays(dataset, feature_fields, target_field)

    if method == "linear":
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = LinearRegression()
        model.fit(X_scaled, y)
        abs_coeffs = np.abs(model.coef_)
        total = np.sum(abs_coeffs)
        importances = abs_coeffs / total if total > 0 else abs_coeffs
    elif method == "random_forest":
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        importances = model.feature_importances_
    else:
        raise AnalysisError(
            code="INVALID_CONSTRAINT",
            message=f"Unknown importance method: {method}",
        )

    return ImportanceResult(
        importances=dict(zip(feature_fields, [float(v) for v in importances])),
        method=method,
    )
