from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, ImportanceResult
from process_opt.analysis.utils import extract_arrays


def compute_importance(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
    method: str = "random_forest",
) -> ImportanceResult:
    X, y = extract_arrays(dataset, feature_fields, target_field)

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
