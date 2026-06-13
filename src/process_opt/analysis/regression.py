from __future__ import annotations

import numpy as np
from sklearn.cross_decomposition import PLSRegression
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, RegressionResult


def _extract_arrays(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
) -> tuple[np.ndarray, np.ndarray]:
    n = dataset.sample_count
    if n == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot fit regression on empty dataset",
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


def _check_nan(X: np.ndarray, y: np.ndarray) -> None:
    if np.any(np.isnan(X)) or np.any(np.isnan(y)):
        raise AnalysisError(
            code="MODEL_FIT_FAILED",
            message="Input data contains NaN values",
            suggestion="Check for missing or invalid values in the dataset",
        )


def fit_regression(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
    model_type: str = "linear",
) -> RegressionResult:
    X, y = _extract_arrays(dataset, feature_fields, target_field)
    _check_nan(X, y)

    try:
        if model_type == "linear":
            model = LinearRegression()
            model.fit(X, y)
            y_pred = model.predict(X)
            coefficients = dict(zip(
                feature_fields,
                [float(c) for c in model.coef_],
            ))
            model_type_label = "linear"
        elif model_type == "pls":
            n_components = min(X.shape[1], X.shape[0] - 1, 5)
            if n_components < 1:
                n_components = 1
            pls = PLSRegression(n_components=n_components)
            pls.fit(X, y)
            y_pred = pls.predict(X).ravel()
            coefficients = dict(zip(
                feature_fields,
                [float(c[0]) for c in pls.coef_],
            ))
            model_type_label = "pls"
        else:
            raise AnalysisError(
                code="INVALID_CONSTRAINT",
                message=f"Unknown model type: {model_type}",
            )
    except Exception as e:
        raise AnalysisError(
            code="MODEL_FIT_FAILED",
            message=f"Model fitting failed: {e}",
        ) from e

    r_squared = float(r2_score(y, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y, y_pred)))

    return RegressionResult(
        r_squared=r_squared,
        rmse=rmse,
        coefficients=coefficients,
        model_type=model_type_label,
    )
