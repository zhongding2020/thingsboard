from __future__ import annotations

import numpy as np

from process_opt.analysis.schemas import AnalysisDataset


class TestProfileDataset:
    def test_profiles_numeric_fields(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        temp = rng.normal(180, 5, n)
        pressure = rng.normal(1.0, 0.1, n)
        features = [
            {"temperature": float(temp[i]), "pressure": float(pressure[i])}
            for i in range(n)
        ]
        targets = [{"diameter": 10.0 + 0.02 * temp[i] + rng.normal(0, 0.1)} for i in range(n)]
        ds = AnalysisDataset(
            features=features,
            targets=targets,
            metadata=[{"barcode": f"B{i}"} for i in range(n)],
            field_summary={},
            sample_count=n,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)

        fields = {r.field for r in results}
        assert "temperature" in fields
        assert "pressure" in fields
        assert "diameter" in fields

    def test_dtype_is_numeric(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": 1.0}, {"x": 2.0}],
            targets=[{"y": 3.0}, {"y": 4.0}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}],
            field_summary={},
            sample_count=2,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        for r in results:
            assert r.dtype == "numeric"

    def test_mean_and_std(self) -> None:
        rng = np.random.default_rng(42)
        n = 1000
        data = rng.normal(50, 10, n)
        features = [{"x": float(data[i])} for i in range(n)]
        targets = [{"y": float(2 * data[i] + rng.normal(0, 1))} for i in range(n)]
        ds = AnalysisDataset(
            features=features,
            targets=targets,
            metadata=[{"barcode": f"B{i}"} for i in range(n)],
            field_summary={},
            sample_count=n,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        result_map = {r.field: r for r in results}
        x_res = result_map["x"]
        assert x_res.mean is not None
        assert abs(x_res.mean - 50) < 1.0
        assert x_res.std is not None
        assert abs(x_res.std - 10) < 1.0

    def test_min_and_max(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": 1.0}, {"x": 5.0}, {"x": 3.0}],
            targets=[{"y": 0.0}, {"y": 0.0}, {"y": 0.0}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}, {"barcode": "B3"}],
            field_summary={},
            sample_count=3,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        result_map = {r.field: r for r in results}
        x_res = result_map["x"]
        assert x_res.min == 1.0
        assert x_res.max == 5.0

    def test_missing_rate(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": 1.0}, {"x": None}, {"x": 3.0}, {"x": None}, {"x": 5.0}],
            targets=[{"y": 0.0}, {"y": 0.0}, {"y": 0.0}, {"y": 0.0}, {"y": 0.0}],
            metadata=[{"barcode": f"B{i}"} for i in range(5)],
            field_summary={},
            sample_count=5,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        result_map = {r.field: r for r in results}
        x_res = result_map["x"]
        assert x_res.missing_count == 2
        assert x_res.missing_rate == 0.4

    def test_iqr_outliers(self) -> None:
        rng = np.random.default_rng(42)
        data = list(rng.normal(100, 10, 100)) + [300.0, 0.0]
        ds = AnalysisDataset(
            features=[{"x": float(v)} for v in data],
            targets=[{"y": 0.0} for _ in data],
            metadata=[{"barcode": f"B{i}"} for i in range(len(data))],
            field_summary={},
            sample_count=len(data),
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        result_map = {r.field: r for r in results}
        x_res = result_map["x"]
        assert x_res.iqr_outliers >= 2

    def test_empty_dataset_returns_empty_list(self) -> None:
        ds = AnalysisDataset(
            features=[],
            targets=[],
            metadata=[],
            field_summary={},
            sample_count=0,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        assert results == []

    def test_field_with_all_missing_values(self) -> None:
        ds = AnalysisDataset(
            features=[{"x": None}, {"x": None}],
            targets=[{"y": 1.0}, {"y": 2.0}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}],
            field_summary={},
            sample_count=2,
        )
        from process_opt.analysis.profiling import profile_dataset

        results = profile_dataset(ds)
        result_map = {r.field: r for r in results}
        x_res = result_map["x"]
        assert x_res.missing_rate == 1.0
        assert x_res.mean is None
        assert x_res.std is None
