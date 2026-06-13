from __future__ import annotations

import numpy as np
import pytest

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import (
    AnalysisDataset,
    Constraint,
    RecommendationRequest,
    RecommendationResult,
)


class TestComputeRecommendation:
    def test_recommended_parameters_within_data_bounds(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        temp = rng.uniform(150, 200, n)
        press = rng.uniform(0.5, 2.0, n)
        diam = 0.05 * temp + 0.5 * press + rng.normal(0, 0.2, n)
        ds = _make_dataset(temp, press, diam)

        req = RecommendationRequest(
            feature_fields=["temperature", "pressure"],
            target_field="diameter",
            target_value=10.0,
        )

        from process_opt.analysis.recommendation import compute_recommendation

        result = compute_recommendation(ds, ["temperature", "pressure"], req)

        assert isinstance(result, RecommendationResult)
        assert "temperature" in result.recommended_parameters
        assert "pressure" in result.recommended_parameters
        assert 140 <= result.recommended_parameters["temperature"] <= 210
        assert 0.4 <= result.recommended_parameters["pressure"] <= 2.2

    def test_respects_fixed_parameter(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        temp = rng.uniform(150, 200, n)
        press = rng.uniform(0.5, 2.0, n)
        diam = 0.05 * temp + 0.5 * press + rng.normal(0, 0.2, n)
        ds = _make_dataset(temp, press, diam)

        req = RecommendationRequest(
            feature_fields=["temperature", "pressure"],
            target_field="diameter",
            target_value=10.0,
        )

        from process_opt.analysis.recommendation import compute_recommendation

        result = compute_recommendation(
            ds, ["temperature", "pressure"], req,
            fixed_parameters={"pressure": 1.0},
        )

        assert result.recommended_parameters["pressure"] == 1.0

    def test_respects_constraints(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        temp = rng.uniform(150, 200, n)
        press = rng.uniform(0.5, 2.0, n)
        diam = 0.05 * temp + 0.5 * press + rng.normal(0, 0.2, n)
        ds = _make_dataset(temp, press, diam)

        req = RecommendationRequest(
            feature_fields=["temperature", "pressure"],
            target_field="diameter",
            target_value=10.0,
            constraints=[Constraint(field="temperature", min=160.0, max=180.0)],
        )

        from process_opt.analysis.recommendation import compute_recommendation

        result = compute_recommendation(ds, ["temperature", "pressure"], req)

        assert 160.0 <= result.recommended_parameters["temperature"] <= 180.0

    def test_alternatives_are_provided(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        temp = rng.uniform(150, 200, n)
        press = rng.uniform(0.5, 2.0, n)
        diam = 0.05 * temp + 0.5 * press + rng.normal(0, 0.2, n)
        ds = _make_dataset(temp, press, diam)

        req = RecommendationRequest(
            feature_fields=["temperature", "pressure"],
            target_field="diameter",
            target_value=10.0,
        )

        from process_opt.analysis.recommendation import compute_recommendation

        result = compute_recommendation(ds, ["temperature", "pressure"], req)

        assert len(result.alternatives) > 0
        for alt in result.alternatives:
            assert "temperature" in alt
            assert "pressure" in alt

    def test_risk_notes_present(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        temp = rng.uniform(150, 200, n)
        press = rng.uniform(0.5, 2.0, n)
        diam = 0.05 * temp + 0.5 * press + rng.normal(0, 0.2, n)
        ds = _make_dataset(temp, press, diam)

        req = RecommendationRequest(
            feature_fields=["temperature", "pressure"],
            target_field="diameter",
            target_value=10.0,
        )

        from process_opt.analysis.recommendation import compute_recommendation

        result = compute_recommendation(ds, ["temperature", "pressure"], req)

        assert isinstance(result.risk_notes, list)

    def test_search_space_too_large_raises_error(self) -> None:
        rng = np.random.default_rng(42)
        n = 50
        vals = {f"x{i}": rng.uniform(0, 1, n) for i in range(20)}
        y = sum(vals.values()) + rng.normal(0, 0.1, n)
        features = [{k: float(vals[k][i]) for k in vals} for i in range(n)]
        targets = [{"y": float(y[i])} for i in range(n)]
        ds = AnalysisDataset(
            features=features, targets=targets,
            metadata=[{"barcode": f"B{i}"} for i in range(n)],
            field_summary={}, sample_count=n,
        )

        req = RecommendationRequest(
            feature_fields=list(vals.keys()),
            target_field="y",
            target_value=5.0,
        )

        from process_opt.analysis.recommendation import compute_recommendation

        with pytest.raises(AnalysisError) as exc:
            compute_recommendation(ds, list(vals.keys()), req)
        assert exc.value.code == "SEARCH_SPACE_TOO_LARGE"

    def test_empty_dataset_raises_error(self) -> None:
        ds = AnalysisDataset(
            features=[], targets=[], metadata=[],
            field_summary={}, sample_count=0,
        )
        req = RecommendationRequest(
            feature_fields=["x"],
            target_field="y",
            target_value=1.0,
        )
        from process_opt.analysis.recommendation import compute_recommendation

        with pytest.raises(AnalysisError) as exc:
            compute_recommendation(ds, ["x"], req)
        assert exc.value.code == "EMPTY_DATASET"


def _make_dataset(temp: np.ndarray, press: np.ndarray, diam: np.ndarray) -> AnalysisDataset:
    n = len(temp)
    features = [{"temperature": float(temp[i]), "pressure": float(press[i])} for i in range(n)]
    targets = [{"diameter": float(diam[i])} for i in range(n)]
    return AnalysisDataset(
        features=features, targets=targets,
        metadata=[{"barcode": f"B{i}"} for i in range(n)],
        field_summary={}, sample_count=n,
    )
