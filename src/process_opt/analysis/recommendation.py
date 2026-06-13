from __future__ import annotations

import itertools

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import (
    AnalysisDataset,
    Constraint,
    RecommendationRequest,
    RecommendationResult,
)

MAX_GRID_COMBINATIONS = 10_000
GRID_STEPS = 10


def _extract_arrays(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    target_field: str,
) -> tuple[np.ndarray, np.ndarray]:
    n = dataset.sample_count
    if n == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot compute recommendation on empty dataset",
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


def _infer_bounds(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    constraints: list[Constraint],
    fixed_parameters: dict[str, float] | None,
) -> tuple[dict[str, float], dict[str, float]]:
    lower: dict[str, float] = {}
    upper: dict[str, float] = {}

    constr_map: dict[str, Constraint] = {c.field: c for c in constraints}

    for field in feature_fields:
        vals = [
            feat[field] for feat in dataset.features
            if isinstance(feat.get(field), (int, float))
        ]
        if not vals:
            raise AnalysisError(
                code="FIELD_NOT_FOUND",
                message=f"No valid values for field '{field}'",
            )

        lo = min(vals)
        hi = max(vals)

        if field in constr_map:
            c = constr_map[field]
            if c.min is not None:
                lo = max(lo, c.min)
            if c.max is not None:
                hi = min(hi, c.max)

        if lo > hi:
            raise AnalysisError(
                code="INVALID_CONSTRAINT",
                message=f"Constraint for '{field}' results in empty range",
            )

        lower[field] = lo
        upper[field] = hi

    return lower, upper


def _generate_grid(
    feature_fields: list[str],
    lower: dict[str, float],
    upper: dict[str, float],
    fixed_parameters: dict[str, float] | None,
) -> list[dict[str, float]]:
    fixed = fixed_parameters or {}
    ranges: list[list[float]] = []
    names: list[str] = []

    for field in feature_fields:
        if field in fixed:
            ranges.append([fixed[field]])
        else:
            vals = np.linspace(lower[field], upper[field], GRID_STEPS).tolist()
            ranges.append(vals)
        names.append(field)

    total = 1
    for r in ranges:
        total *= len(r)
    if total > MAX_GRID_COMBINATIONS:
        raise AnalysisError(
            code="SEARCH_SPACE_TOO_LARGE",
            message=f"Search space of {total} combinations exceeds limit of {MAX_GRID_COMBINATIONS}",
            suggestion="Reduce the number of parameters or increase grid step size",
        )

    grid: list[dict[str, float]] = []
    for combo in itertools.product(*ranges):
        grid.append(dict(zip(names, combo)))
    return grid


def _generate_risk_notes(
    rec: dict[str, float],
    lower: dict[str, float],
    upper: dict[str, float],
) -> list[str]:
    notes: list[str] = []
    for field, val in rec.items():
        margin_lo = (val - lower[field]) / (upper[field] - lower[field]) if upper[field] != lower[field] else 0
        margin_hi = (upper[field] - val) / (upper[field] - lower[field]) if upper[field] != lower[field] else 0
        if margin_lo < 0.1:
            notes.append(f"{field} is near its lower bound ({val:.2f})")
        if margin_hi < 0.1:
            notes.append(f"{field} is near its upper bound ({val:.2f})")
    return notes


def compute_recommendation(
    dataset: AnalysisDataset,
    feature_fields: list[str],
    request: RecommendationRequest,
    fixed_parameters: dict[str, float] | None = None,
) -> RecommendationResult:
    X, y = _extract_arrays(dataset, feature_fields, request.target_field)

    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)
    r_sq = float(r2_score(y, y_pred))

    lower, upper = _infer_bounds(dataset, feature_fields, request.constraints, fixed_parameters)
    grid = _generate_grid(feature_fields, lower, upper, fixed_parameters)

    grid_X = np.array([[p[f] for f in feature_fields] for p in grid], dtype=np.float64)
    predictions = model.predict(grid_X)

    scored = list(zip(grid, [float(p) for p in predictions]))
    scored.sort(key=lambda x: abs(x[1] - request.target_value))

    if not scored:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="No valid candidates after applying constraints",
        )

    best_params, best_pred = scored[0]

    alternatives = [params for params, _ in scored[1:6]]

    risk_notes = _generate_risk_notes(best_params, lower, upper)

    return RecommendationResult(
        recommended_parameters=best_params,
        predicted_target=best_pred,
        alternatives=alternatives,
        important_features=feature_fields,
        risk_notes=risk_notes,
        model_metrics={"r_squared": r_sq, "rmse": float(np.sqrt(np.mean((y - y_pred) ** 2)))},
        dataset_summary={"sample_count": dataset.sample_count, "feature_count": len(feature_fields)},
    )
