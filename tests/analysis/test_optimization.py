from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, OptimizationConfig


def _make_dataset(
    x1: np.ndarray, x2: np.ndarray, y: np.ndarray,
) -> AnalysisDataset:
    n = len(x1)
    features = [
        {"temp": float(x1[i]), "pressure": float(x2[i])}
        for i in range(n)
    ]
    targets = [{"strength": float(y[i])} for i in range(n)]
    return AnalysisDataset(
        features=features, targets=targets,
        metadata=[{} for _ in range(n)],
        field_summary={}, sample_count=n,
    )


class TestRunOptimization:
    def test_returns_optimization_result(self) -> None:
        rng = np.random.default_rng(42)
        n = 200
        temp = rng.uniform(150, 250, n)
        pressure = rng.uniform(1.0, 5.0, n)
        strength = 100 + 0.3 * (temp - 200) - 5 * (pressure - 3) + rng.normal(0, 2, n)

        ds = _make_dataset(temp, pressure, strength)

        config = OptimizationConfig(
            dataset_id="test",
            target_field="strength",
            usl=115.0,
            lsl=85.0,
            target_value=100.0,
            target_cpk=1.33,
            key_factors=["temp", "pressure"],
            step_size=5.0,
            max_iterations=1000,
        )

        from process_opt.analysis.optimization import run_optimization

        result = run_optimization(ds, config)

        assert result.target_field == "strength"
        assert result.optimized_cpk > 0
        assert len(result.convergence) > 0
        assert "temp" in result.recommended_params
        assert "pressure" in result.recommended_params
        assert result.initial_cpk > 0
