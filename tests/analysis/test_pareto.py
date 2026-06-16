from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset


class TestComputePareto:
    def test_returns_items_sorted_by_coefficient(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1: list[float] = rng.normal(0, 1, n).tolist()
        x2: list[float] = rng.normal(0, 1, n).tolist()
        x3: list[float] = rng.normal(0, 1, n).tolist()
        y: list[float] = [x1[i] * 2 + rng.normal(0, 0.3) for i in range(n)]

        features = [{"x1": x1[i], "x2": x2[i], "x3": x3[i]} for i in range(n)]
        targets = [{"y": y[i]} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{} for _ in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.pareto import compute_pareto

        items = compute_pareto(ds, "y")

        assert len(items) == 3
        coeffs = [i.coefficient for i in items]
        assert coeffs == sorted(coeffs, reverse=True)

    def test_cumulative_pct_sums_to_100(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y = x1 + x2 + rng.normal(0, 0.2, n)

        features = [{"x1": float(x1[i]), "x2": float(x2[i])} for i in range(n)]
        targets = [{"y": float(y[i])} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{} for _ in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.pareto import compute_pareto

        items = compute_pareto(ds, "y")

        assert pytest.approx(items[-1].cumulative_pct, 0.01) == 100.0

    def test_empty_dataset_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[], targets=[], metadata=[],
            field_summary={}, sample_count=0,
        )

        from process_opt.analysis.pareto import compute_pareto

        with pytest.raises(AnalysisError) as exc:
            compute_pareto(ds, "y")
        assert exc.value.code == "EMPTY_DATASET"

    def test_nonnumeric_target_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": 1.0}, {"x": 2.0}],
            targets=[{"y": "abc"}, {"y": "def"}],
            metadata=[{} for _ in range(2)],
            field_summary={}, sample_count=2,
        )
        from process_opt.analysis.pareto import compute_pareto
        with pytest.raises(AnalysisError) as exc:
            compute_pareto(ds, "y")
        assert exc.value.code == "NON_NUMERIC_FIELD"

    def test_strength_classification(self) -> None:
        rng = np.random.default_rng(42)
        n = 200
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n) * 0.5
        y = x1 * 3 + rng.normal(0, 0.3, n)

        features = [{"x1": float(x1[i]), "x2": float(x2[i])} for i in range(n)]
        targets = [{"y": float(y[i])} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{} for _ in range(n)],
            field_summary={}, sample_count=n,
        )
        from process_opt.analysis.pareto import compute_pareto
        items = compute_pareto(ds, "y")
        strengths = {i.field: i.strength for i in items}
        assert strengths["x1"] == "strong"
