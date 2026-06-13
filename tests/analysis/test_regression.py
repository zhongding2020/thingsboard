from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset


class TestFitRegression:
    def test_linear_returns_high_r_squared(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = 2 * x1 + 3 * x2 + rng.normal(0, 0.5, n)
        ds = _make_dataset(x1, x2, y)

        from process_opt.analysis.regression import fit_regression

        result = fit_regression(ds, ["x1", "x2"], "y", model_type="linear")

        assert result.r_squared > 0.8
        assert result.model_type == "linear"
        assert set(result.coefficients.keys()) == {"x1", "x2"}

    def test_linear_coefficients_approx_expected(self) -> None:
        rng = np.random.default_rng(42)
        n = 500
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = 2 * x1 + 3 * x2 + rng.normal(0, 0.2, n)
        ds = _make_dataset(x1, x2, y)

        from process_opt.analysis.regression import fit_regression

        result = fit_regression(ds, ["x1", "x2"], "y", model_type="linear")

        assert abs(result.coefficients["x1"] - 2) < 0.5
        assert abs(result.coefficients["x2"] - 3) < 0.5

    def test_pls_returns_model_type_containing_pls(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = 2 * x1 + 3 * x2 + rng.normal(0, 0.5, n)
        ds = _make_dataset(x1, x2, y)

        from process_opt.analysis.regression import fit_regression

        result = fit_regression(ds, ["x1", "x2"], "y", model_type="pls")

        assert "pls" in result.model_type.lower()
        assert result.r_squared > 0.8

    def test_empty_dataset_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[], targets=[], metadata=[],
            field_summary={}, sample_count=0,
        )
        from process_opt.analysis.regression import fit_regression

        with pytest.raises(AnalysisError) as exc:
            fit_regression(ds, ["x"], "y")
        assert exc.value.code == "EMPTY_DATASET"

    def test_model_fit_failed_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": 1.0}, {"x": 2.0}, {"x": 3.0}],
            targets=[{"y": float("nan")}, {"y": 2.0}, {"y": float("nan")}],
            metadata=[{"barcode": f"B{i}"} for i in range(3)],
            field_summary={}, sample_count=3,
        )
        from process_opt.analysis.regression import fit_regression

        with pytest.raises(AnalysisError) as exc:
            fit_regression(ds, ["x"], "y", model_type="linear")
        assert exc.value.code == "MODEL_FIT_FAILED"


def _make_dataset(x1: np.ndarray, x2: np.ndarray, y: np.ndarray) -> AnalysisDataset:
    n = len(x1)
    features = [{"x1": float(x1[i]), "x2": float(x2[i])} for i in range(n)]
    targets = [{"y": float(y[i])} for i in range(n)]
    return AnalysisDataset(
        features=features, targets=targets,
        metadata=[{"barcode": f"B{i}"} for i in range(n)],
        field_summary={}, sample_count=n,
    )
