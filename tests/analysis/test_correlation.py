from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset


class TestComputeCorrelation:
    def test_pearson_positive_correlation(self) -> None:
        rng = np.random.default_rng(42)
        x = np.linspace(0, 10, 50)
        y = 2 * x + rng.normal(0, 0.5, 50)
        ds = _make_dataset(x, y)

        from process_opt.analysis.correlation import compute_correlation

        results = compute_correlation(ds, ["x"], ["y"], method="pearson")

        assert len(results) == 1
        r = results[0]
        assert r.field_x == "x"
        assert r.field_y == "y"
        assert r.method == "pearson"
        assert r.coefficient > 0.9
        assert r.p_value < 0.001

    def test_pearson_negative_correlation(self) -> None:
        rng = np.random.default_rng(42)
        x = np.linspace(0, 10, 50)
        y = -3 * x + rng.normal(0, 0.5, 50)
        ds = _make_dataset(x, y)

        from process_opt.analysis.correlation import compute_correlation

        results = compute_correlation(ds, ["x"], ["y"], method="pearson")

        assert len(results) == 1
        r = results[0]
        assert r.coefficient < -0.9

    def test_pearson_no_correlation(self) -> None:
        rng = np.random.default_rng(42)
        x = np.linspace(0, 10, 50)
        y = rng.normal(0, 1, 50)
        ds = _make_dataset(x, y)

        from process_opt.analysis.correlation import compute_correlation

        results = compute_correlation(ds, ["x"], ["y"], method="pearson")

        assert len(results) == 1
        r = results[0]
        assert abs(r.coefficient) < 0.3
        assert r.p_value > 0.01

    def test_spearman_rank_correlation(self) -> None:
        x = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
        y = np.array([10, 9, 8, 7, 6, 5, 4, 3, 2, 1], dtype=float)
        ds = _make_dataset(x, y)

        from process_opt.analysis.correlation import compute_correlation

        results = compute_correlation(ds, ["x"], ["y"], method="spearman")

        assert len(results) == 1
        r = results[0]
        assert r.method == "spearman"
        assert r.coefficient < -0.9

    def test_multiple_features_and_targets(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        y1 = x1 + rng.normal(0, 0.2, n)
        y2 = x2 + rng.normal(0, 0.2, n)

        features = [{"x1": float(x1[i]), "x2": float(x2[i])} for i in range(n)]
        targets = [{"y1": float(y1[i]), "y2": float(y2[i])} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{"barcode": f"B{i}"} for i in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.correlation import compute_correlation

        results = compute_correlation(ds, ["x1", "x2"], ["y1", "y2"], method="pearson")

        assert len(results) == 4
        result_map = {(r.field_x, r.field_y): r for r in results}
        assert ("x1", "y1") in result_map
        assert ("x2", "y2") in result_map

    def test_results_sorted_by_abs_coefficient(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.normal(0, 1, n)
        x2 = rng.normal(0, 1, n)
        x3 = rng.normal(0, 1, n)
        strong = x1 + rng.normal(0, 0.1, n)
        weak = x2 + rng.normal(0, 2, n)
        none = x3

        features = [{"x1": float(x1[i]), "x2": float(x2[i]), "x3": float(x3[i])} for i in range(n)]
        targets = [{"strong": float(strong[i]), "weak": float(weak[i]), "none": float(none[i])}
                   for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{"barcode": f"B{i}"} for i in range(n)],
            field_summary={}, sample_count=n,
        )

        from process_opt.analysis.correlation import compute_correlation

        results = compute_correlation(ds, ["x1", "x2", "x3"], ["strong", "weak", "none"], method="pearson")

        coeffs = [abs(r.coefficient) for r in results]
        assert coeffs == sorted(coeffs, reverse=True)

    def test_empty_dataset_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[], targets=[], metadata=[],
            field_summary={}, sample_count=0,
        )
        from process_opt.analysis.correlation import compute_correlation

        with pytest.raises(AnalysisError) as exc:
            compute_correlation(ds, ["x"], ["y"], method="pearson")
        assert exc.value.code == "EMPTY_DATASET"

    def test_nonnumeric_field_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": "abc"}, {"x": "def"}],
            targets=[{"y": 1.0}, {"y": 2.0}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}],
            field_summary={}, sample_count=2,
        )
        from process_opt.analysis.correlation import compute_correlation

        with pytest.raises(AnalysisError) as exc:
            compute_correlation(ds, ["x"], ["y"], method="pearson")
        assert exc.value.code == "NON_NUMERIC_FIELD"


def _make_dataset(x: np.ndarray, y: np.ndarray) -> AnalysisDataset:
    n = len(x)
    features = [{"x": float(x[i])} for i in range(n)]
    targets = [{"y": float(y[i])} for i in range(n)]
    return AnalysisDataset(
        features=features, targets=targets,
        metadata=[{"barcode": f"B{i}"} for i in range(n)],
        field_summary={}, sample_count=n,
    )
