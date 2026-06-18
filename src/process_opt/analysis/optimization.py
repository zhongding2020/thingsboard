from __future__ import annotations

import math

import numpy as np
from sklearn.linear_model import LinearRegression

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, OptimizationConfig, OptimizationResult
from process_opt.analysis.utils import extract_arrays


def _compute_cpk(y_pred: float, usl: float, lsl: float, rmse: float) -> float:
    if rmse <= 0 or y_pred <= lsl or y_pred >= usl:
        return 0.0
    sigma = rmse
    cpu = (usl - y_pred) / (3 * sigma)
    cpl = (y_pred - lsl) / (3 * sigma)
    return min(cpu, cpl)


def run_optimization(
    dataset: AnalysisDataset,
    config: OptimizationConfig,
) -> OptimizationResult:
    if dataset.sample_count == 0:
        raise AnalysisError(
            code="EMPTY_DATASET",
            message="Cannot run optimization on empty dataset",
        )

    X, y = extract_arrays(dataset, config.key_factors, config.target_field)
    if np.any(np.isnan(X)) or np.any(np.isnan(y)):
        raise AnalysisError(
            code="MODEL_FIT_FAILED",
            message="Input data contains NaN values",
            suggestion="Check for missing or invalid values in the dataset",
        )
    model = LinearRegression()
    model.fit(X, y)
    y_pred_all = model.predict(X)
    rmse = float(np.sqrt(np.mean((y - y_pred_all) ** 2)))

    bounds: dict[str, tuple[float, float]] = {}
    for j, field in enumerate(config.key_factors):
        col = X[:, j]
        bounds[field] = (float(col.min()), float(col.max()))

    initial_params = {field: float(X[:, j].mean()) for j, field in enumerate(config.key_factors)}
    X_init = np.array([[initial_params[f] for f in config.key_factors]], dtype=np.float64)
    y_init_pred = float(model.predict(X_init)[0])
    initial_cpk = _compute_cpk(y_init_pred, config.usl, config.lsl, rmse)

    current_params = initial_params.copy()
    current_X = np.array([[current_params[f] for f in config.key_factors]], dtype=np.float64)
    current_y_pred = float(model.predict(current_X)[0])
    current_cpk = _compute_cpk(current_y_pred, config.usl, config.lsl, rmse)
    current_loss = _loss(current_cpk, current_y_pred, config)

    best_params = current_params.copy()
    best_loss = current_loss

    T0 = 100.0
    alpha = 0.95
    convergence: list[dict[str, float]] = []

    for iteration in range(config.max_iterations):
        T = T0 * (alpha ** iteration)

        new_params = current_params.copy()
        for field in config.key_factors:
            step = config.step_size * (T / T0)
            lo, hi = bounds[field]
            delta = np.random.uniform(-step, step)
            new_params[field] = max(lo, min(hi, new_params[field] + delta))

        new_X = np.array([[new_params[f] for f in config.key_factors]], dtype=np.float64)
        new_y_pred = float(model.predict(new_X)[0])
        new_cpk = _compute_cpk(new_y_pred, config.usl, config.lsl, rmse)
        new_loss = _loss(new_cpk, new_y_pred, config)

        delta_loss = new_loss - current_loss

        if delta_loss < 0 or (T > 0 and np.random.random() < math.exp(-delta_loss / max(T, 1e-10))):
            current_params = new_params
            current_y_pred = new_y_pred
            current_cpk = new_cpk
            current_loss = new_loss

            if current_loss < best_loss:
                best_params = current_params.copy()
                best_loss = current_loss

        if iteration % 50 == 0 or iteration == config.max_iterations - 1:
            convergence.append({"iteration": iteration, "cpk_value": round(current_cpk, 4)})

    best_X = np.array([[best_params[f] for f in config.key_factors]], dtype=np.float64)
    best_y_pred = float(model.predict(best_X)[0])
    optimized_cpk = _compute_cpk(best_y_pred, config.usl, config.lsl, rmse)

    adjustments: dict[str, dict[str, float]] = {}
    for field in config.key_factors:
        orig = initial_params[field]
        opt = best_params[field]
        adjustments[field] = {
            "from": round(orig, 2),
            "to": round(opt, 2),
            "delta": round(opt - orig, 2),
        }

    return OptimizationResult(
        initial_cpk=round(initial_cpk, 4),
        optimized_cpk=round(optimized_cpk, 4),
        convergence=convergence,
        recommended_params={k: round(v, 4) for k, v in best_params.items()},
        parameter_adjustments=adjustments,
        target_field=config.target_field,
    )


def _loss(cpk: float, y_pred: float, config: OptimizationConfig) -> float:
    if cpk < config.target_cpk:
        return (config.target_cpk - cpk) ** 2
    else:
        return abs(y_pred - config.target_value)
