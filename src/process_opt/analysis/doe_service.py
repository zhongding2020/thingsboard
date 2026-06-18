from __future__ import annotations

import logging

import numpy as np
from pyDOE2 import (
    bbdesign,
    ccdesign,
    ff2n,
    fracfact,
    fullfact,
)
from scipy import stats
from sklearn.linear_model import LinearRegression

from process_opt.analysis.doe_schemas import (
    ANOVARequest,
    ANOVAResult,
    DOEConfig,
    DOEDesign,
    DOERun,
    ExperimentResult,
    FactorEffect,
)

logger = logging.getLogger(__name__)


def generate_design(config: DOEConfig) -> DOEDesign:
    k = len(config.factors)
    levels = [2] * k

    if config.method == "full_factorial":
        matrix = fullfact(levels)
    elif config.method == "frac_factorial":
        if k <= 3:
            matrix = fullfact(levels)
        else:
            gen = _default_generator(k)
            matrix = fracfact(gen)
    elif config.method == "central_composite":
        alpha = config.alpha or "orthogonal"
        centers = max(config.center_points, 1)
        matrix = ccdesign(k, center=(centers, centers), alpha=alpha, face="ccc")
    elif config.method == "box_behnken":
        centers = max(config.center_points, 1)
        matrix = bbdesign(k, center=centers)
    elif config.method == "taguchi":
        matrix = _taguchi_design(k)
    else:
        raise ValueError(f"Unsupported design method: {config.method}")

    matrix_2d = np.atleast_2d(matrix)

    n_runs = matrix_2d.shape[0]
    runs: list[DOERun] = []
    design_matrix: list[list[float]] = []

    for i in range(n_runs):
        coded = matrix_2d[i].tolist()
        factor_vals: dict[str, float] = {}
        real_vals: list[float] = []
        for j, f in enumerate(config.factors):
            val = f.low if coded[j] <= 0 else f.high
            factor_vals[f.name] = val
            real_vals.append(val)
        runs.append(
            DOERun(run_order=i + 1, standard_order=i + 1, factor_values=factor_vals)
        )
        design_matrix.append(real_vals)

    if config.replicates and config.replicates > 1:
        original_runs = list(runs)
        original_matrix = list(design_matrix)
        for rep in range(1, config.replicates):
            for run in original_runs:
                runs.append(DOERun(
                    run_order=len(runs) + 1,
                    standard_order=run.standard_order,
                    factor_values=dict(run.factor_values),
                    replicate=rep + 1,
                ))
            design_matrix.extend([list(row) for row in original_matrix])

    return DOEDesign(
        method=config.method,
        factors=config.factors,
        runs=runs,
        run_count=len(runs),
        design_matrix=design_matrix,
    )


def run_anova(request: ANOVARequest) -> ANOVAResult:
    k = len(request.factors)
    factor_names = [f.name for f in request.factors]

    design_matrix = np.array([list(r.factor_values.values()) for r in request.design_runs])
    response = np.array([r.response for r in request.results])

    X_list: list[np.ndarray] = []
    effect_labels: list[str] = []

    X = np.ones((len(response), 1))
    effect_labels.append("intercept")

    scaled = np.zeros_like(design_matrix)
    for j in range(k):
        col = design_matrix[:, j]
        lo = np.min(col)
        hi = np.max(col)
        if hi > lo:
            scaled[:, j] = (col - lo) / (hi - lo) * 2 - 1
        else:
            scaled[:, j] = col

    for j in range(k):
        X = np.column_stack([X, scaled[:, j]])
        effect_labels.append(factor_names[j])

    for inter in request.interactions:
        if len(inter) == 2 and inter[0] in factor_names and inter[1] in factor_names:
            i1 = factor_names.index(inter[0])
            i2 = factor_names.index(inter[1])
            X = np.column_stack([X, scaled[:, i1] * scaled[:, i2]])
            effect_labels.append(f"{inter[0]}:{inter[1]}")

    model = LinearRegression()
    model.fit(X, response)
    y_pred = model.predict(X)
    residuals = response - y_pred

    n = len(response)
    p = X.shape[1]
    dof = n - p

    ss_total = np.sum((response - np.mean(response)) ** 2)
    ss_residual = np.sum(residuals**2)
    r_squared = 1 - ss_residual / ss_total if ss_total > 0 else 0
    adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - p) if n > p else 0

    sigma2 = ss_residual / dof if dof > 0 else 0
    cov = np.linalg.inv(X.T @ X) * sigma2
    se = np.sqrt(np.diag(cov))

    effects: list[FactorEffect] = []
    for i, label in enumerate(effect_labels):
        coef = model.coef_[i] if i < len(model.coef_) else 0
        std_err = se[i] if i < len(se) else 0
        t_val = coef / std_err if std_err > 1e-10 else 0
        p_val = 2 * stats.t.sf(abs(t_val), dof) if dof > 0 else 1.0

        effects.append(
            FactorEffect(
                factor=label,
                effect=coef * 2 if i > 0 else coef,
                coefficient=round(float(coef), 4),
                std_error=round(float(std_err), 4),
                t_value=round(float(t_val), 4),
                p_value=round(float(p_val), 4),
                significant=p_val < 0.05,
            )
        )

    sig_count = sum(1 for e in effects[1:] if e.significant)

    summary_parts = [
        f"拟合模型含 {p} 个参数，样本数 {n}",
        f"R²={r_squared:.4f}，Adj R²={adj_r_squared:.4f}",
    ]
    if sig_count > 0:
        summary_parts.append(f"显著因子 {sig_count} 个: {', '.join(e.factor for e in effects[1:] if e.significant)}")

    return ANOVAResult(
        response_name=request.response_name,
        effects=effects,
        r_squared=round(float(r_squared), 4),
        adj_r_squared=round(float(adj_r_squared), 4),
        model_significant=sig_count > 0,
        summary="；".join(summary_parts),
    )


def _default_generator(k: int) -> str:
    generators = {
        4: "a b c abc",
        5: "a b c d abcd",
        6: "a b c d e abcde",
        7: "a b c d e f abcdef",
        8: "a b c d e f g abcdefg",
    }
    return generators.get(k, " ".join(chr(97 + i) for i in range(k)))


def _taguchi_design(k: int) -> np.ndarray:
    if k == 2:
        return np.array([[1, 1], [1, 2], [2, 1], [2, 2]])
    if k == 3:
        return np.array([
            [1, 1, 1], [1, 2, 2], [1, 3, 3],
            [2, 1, 2], [2, 2, 3], [2, 3, 1],
            [3, 1, 3], [3, 2, 1], [3, 3, 2],
        ])
    return fullfact([2] * k)
