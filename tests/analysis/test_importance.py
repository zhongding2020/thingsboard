from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset


class TestComputeImportance:
    def test_linear_returns_higher_importance_for_stronger_feature(self) -> None:
        rng = np.random.default_rng(42)
        n = 200
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = 5 * x1 + 0.1 * x2 + rng.normal(0, 0.5, n)
        ds = _make_dataset(x1, x2, y)

        from process_opt.analysis.importance import compute_importance

        result = compute_importance(ds, ["x1", "x2"], "y", method="linear")

        assert result.method == "linear"
        assert result.importances["x1"] > result.importances["x2"]

    def test_random_forest_returns_higher_importance_for_stronger_feature(self) -> None:
        rng = np.random.default_rng(42)
        n = 200
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = 5 * x1 + 0.1 * x2 + rng.normal(0, 0.5, n)
        ds = _make_dataset(x1, x2, y)

        from process_opt.analysis.importance import compute_importance

        result = compute_importance(ds, ["x1", "x2"], "y", method="random_forest")

        assert result.method == "random_forest"
        assert result.importances["x1"] > result.importances["x2"]

    def test_importances_sum_to_one_for_random_forest(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        x3 = rng.normal(0, 1, n)
        y = x1 + x2 + rng.normal(0, 0.1, n)
        ds = _make_dataset(x1, x2, x3, y)

        from process_opt.analysis.importance import compute_importance

        result = compute_importance(ds, ["x1", "x2", "x3"], "y", method="random_forest")
        total = sum(result.importances.values())
        assert abs(total - 1.0) < 0.01

    def test_empty_dataset_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[], targets=[], metadata=[],
            field_summary={}, sample_count=0,
        )
        from process_opt.analysis.importance import compute_importance

        with pytest.raises(AnalysisError) as exc:
            compute_importance(ds, ["x"], "y")
        assert exc.value.code == "EMPTY_DATASET"

    def test_nonnumeric_field_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": "abc"}, {"x": "def"}],
            targets=[{"y": 1.0}, {"y": 2.0}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}],
            field_summary={}, sample_count=2,
        )
        from process_opt.analysis.importance import compute_importance

        with pytest.raises(AnalysisError) as exc:
            compute_importance(ds, ["x"], "y", method="linear")
        assert exc.value.code == "NON_NUMERIC_FIELD"


def _make_dataset(*arrs: np.ndarray) -> AnalysisDataset:
    n = len(arrs[0])
    y_arr = arrs[-1]
    x_arrs = arrs[:-1]
    features: list[dict[str, float]] = []
    for i in range(n):
        feat: dict[str, float] = {}
        for j, x in enumerate(x_arrs):
            feat[f"x{j + 1}"] = float(x[i])
        features.append(feat)
    targets = [{"y": float(y_arr[i])} for i in range(n)]
    return AnalysisDataset(
        features=features, targets=targets,
        metadata=[{"barcode": f"B{i}"} for i in range(n)],
        field_summary={}, sample_count=n,
    )
