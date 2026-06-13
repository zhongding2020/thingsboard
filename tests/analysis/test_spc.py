from __future__ import annotations

import numpy as np

from process_opt.analysis.schemas import AnalysisDataset
from process_opt.analysis.spc import (
    build_spc_result,
    compute_capability,
    compute_histogram,
    compute_imr,
    compute_overview,
    compute_p_chart,
    compute_summary,
)


class TestComputeImr:
    def test_returns_i_and_mr_charts(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 50)]
        labels = [f"B{i}" for i in range(50)]
        i_chart, mr_chart = compute_imr(vals, labels)
        assert len(i_chart.values) == 50
        assert len(i_chart.labels) == 50
        assert i_chart.ucl > i_chart.mean
        assert i_chart.lcl < i_chart.mean
        assert len(mr_chart.values) == 49
        assert mr_chart.ucl > 0

    def test_identifies_out_of_control_points(self) -> None:
        vals = [100.0] * 20 + [300.0, 100.0]
        labels = [f"B{i}" for i in range(22)]
        i_chart, _ = compute_imr(vals, labels)
        assert 20 in i_chart.alerts

    def test_empty_values(self) -> None:
        i_chart, mr_chart = compute_imr([], [])
        assert i_chart.values == []
        assert mr_chart.values == []


class TestComputeCapability:
    def test_returns_indices(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 100)]
        cap = compute_capability(vals, 115, 85)
        assert cap.cp > 0
        assert cap.cpk > 0
        assert cap.pp > 0
        assert cap.ppk > 0
        assert cap.usl == 115
        assert cap.lsl == 85

    def test_perfect_process_has_high_cpk(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 0.5, 100)]
        cap = compute_capability(vals, 110, 90)
        assert cap.cpk > 1.5


class TestComputeHistogram:
    def test_returns_bins_and_curve(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 200)]
        hist = compute_histogram(vals, 115, 85)
        assert len(hist.bins) == 20
        assert len(hist.counts) == 20
        assert len(hist.curve_x) == 200
        assert len(hist.curve_y) == 200


class TestComputePChart:
    def test_returns_defect_rates(self) -> None:
        results = ["pass", "pass", "fail", "pass", "fail", "pass", "pass", "pass", "fail", "pass"]
        groups = ["2026-06-01"] * 5 + ["2026-06-02"] * 5
        p = compute_p_chart(results, groups)
        assert len(p.periods) == 2
        assert p.defect_count == 3
        assert p.total_count == 10
        assert p.p_bar == 0.3

    def test_no_results(self) -> None:
        p = compute_p_chart([], [])
        assert p.periods == []


class TestComputeSummary:
    def test_returns_stats(self) -> None:
        rng = np.random.default_rng(42)
        vals = [float(v) for v in rng.normal(100, 5, 100)]
        s = compute_summary(vals)
        assert s.n == 100
        assert 90 < s.mean < 110
        assert s.std > 0
        assert s.min_val < s.max_val

    def test_normality_p_is_none_for_small_samples(self) -> None:
        s = compute_summary([1.0, 2.0, 3.0])
        assert s.normality_p is None


class TestBuildSpcResult:
    def test_overview_only_when_no_field(self) -> None:
        ds = AnalysisDataset(
            features=[{"temperature": 180.0}, {"temperature": 190.0}],
            targets=[{"quality": "pass"}, {"quality": "pass"}],
            metadata=[{"barcode": "B1"}, {"barcode": "B2"}],
            field_summary={},
            sample_count=2,
        )
        result = build_spc_result(overview_dataset=ds, field_dataset=ds, field=None, usl=None, lsl=None, target=None)
        assert len(result.overview) > 0
        assert result.i_chart is None

    def test_full_result_with_field(self) -> None:
        ds = AnalysisDataset(
            features=[{"temperature": 180.0}, {"temperature": 190.0}, {"temperature": 200.0}],
            targets=[{"quality": "pass"}, {"quality": "pass"}, {"quality": "fail"}],
            metadata=[{"barcode": "B1", "processed_at": "2026-06-01T00:00:00Z"},
                      {"barcode": "B2", "processed_at": "2026-06-01T00:00:00Z"},
                      {"barcode": "B3", "processed_at": "2026-06-02T00:00:00Z"}],
            field_summary={},
            sample_count=3,
        )
        result = build_spc_result(overview_dataset=ds, field_dataset=ds, field="temperature", usl=210.0, lsl=170.0, target=190.0)
        assert result.i_chart is not None
        assert len(result.i_chart.values) == 3
        assert result.capability is not None
        assert result.capability.usl == 210.0
        assert result.capability.lsl == 170.0
        assert result.p_chart is not None
        assert result.summary is not None
        assert result.summary.n == 3
