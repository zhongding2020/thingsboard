from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.app import create_app
from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import (
    AnalysisDataset,
    AnalysisDatasetRequest,
    Capability,
    CorrelationRequest,
    CorrelationResult,
    Histogram,
    IChart,
    ImportanceRequest,
    ImportanceResult,
    MrChart,
    ParamOverview,
    PChart,
    ProfilingResult,
    RecommendationRequest,
    RecommendationResult,
    RegressionRequest,
    RegressionResult,
    SpcRequest,
    SpcResult,
    SummaryStats,
)
from process_opt.parameters.schemas import (
    ParameterSet,
    ParameterSetCreate,
    ParameterSetWithItems,
    ParameterStatus,
)


class FakeAnalysisService:
    def __init__(self) -> None:
        self.profile_called_with: list[AnalysisDataset] = []
        self.correlation_called_with: list[CorrelationRequest] = []
        self.importance_called_with: list[ImportanceRequest] = []
        self.regression_called_with: list[RegressionRequest] = []
        self.recommendation_called_with: list[RecommendationRequest] = []
        self.fail_on: str | None = None

    async def profile(self, dataset: AnalysisDataset) -> list[ProfilingResult]:
        self.profile_called_with.append(dataset)
        if self.fail_on == "profile":
            raise AnalysisError("EMPTY_DATASET", "Dataset is empty", suggestion="Add more data")
        return [ProfilingResult(field="temp", mean=180.0, std=5.0, count=10)]

    async def profile_from_request(self, request: AnalysisDatasetRequest) -> list[ProfilingResult]:
        return await self.profile(
            AnalysisDataset(features=[], targets=[], metadata=[], field_summary={}, sample_count=0)
        )

    async def correlation(self, request: CorrelationRequest) -> CorrelationResult:
        self.correlation_called_with.append(request)
        if self.fail_on == "correlation":
            raise AnalysisError(
                "FIELD_NOT_FOUND",
                "Field missing",
                details={"field": "x"},
                suggestion="Check field names",
            )
        return CorrelationResult(
            field_x="a", field_y="b", coefficient=0.9, p_value=0.01, method="pearson"
        )

    async def importance(self, request: ImportanceRequest) -> ImportanceResult:
        self.importance_called_with.append(request)
        if self.fail_on == "importance":
            raise AnalysisError("INSUFFICIENT_SAMPLES", "Need more samples", suggestion="Collect more data")
        return ImportanceResult(importances={"temp": 0.8}, method="random_forest")

    async def regression(self, request: RegressionRequest) -> RegressionResult:
        self.regression_called_with.append(request)
        if self.fail_on == "regression":
            raise AnalysisError("MODEL_FIT_FAILED", "Model failed", suggestion="Try different model")
        return RegressionResult(
            r_squared=0.95, rmse=0.1, coefficients={"temp": 1.5}, model_type="linear"
        )

    async def recommendation(self, request: RecommendationRequest) -> RecommendationResult:
        self.recommendation_called_with.append(request)
        if self.fail_on == "recommendation":
            raise AnalysisError(
                "SEARCH_SPACE_TOO_LARGE", "Too many combos", suggestion="Reduce parameters"
            )
        return RecommendationResult(
            recommended_parameters={"temp": 180},
            predicted_target=90.0,
            alternatives=[{"temp": 175}],
            important_features=["temp"],
            risk_notes=["temp is near lower bound"],
            model_metrics={"r_squared": 0.9},
            dataset_summary={"sample_count": 10},
        )

    async def spc(self, request: SpcRequest) -> SpcResult:
        if request.field is None:
            return SpcResult(
                overview=[
                    ParamOverview(
                        field="temperature", n=10, mean=200.0, std=5.0,
                        usl=215.0, lsl=185.0, cpk=1.0, outlier_count=0, status="marginal",
                    )
                ],
            )
        return SpcResult(
            overview=[
                ParamOverview(
                    field="temperature", n=10, mean=200.0, std=5.0,
                    usl=215.0, lsl=185.0, cpk=1.0, outlier_count=0, status="marginal",
                )
            ],
            i_chart=IChart(values=[200.0], labels=["B1"], mean=200.0, ucl=215.0, lcl=185.0, alerts=[]),
            mr_chart=MrChart(values=[], labels=[], mr_bar=0.0, ucl=0.0),
            histogram=Histogram(bins=[], counts=[], curve_x=[], curve_y=[]),
            capability=Capability(cp=1.0, cpk=1.0, pp=1.0, ppk=1.0, usl=215.0, lsl=185.0),
            p_chart=PChart(periods=[], rates=[], total_count=0, defect_count=0, ucl=0.0, p_bar=0.0),
            summary=SummaryStats(n=1, mean=200.0, std=0.0, min_val=200.0, max_val=200.0, normality_p=None),
        )


class FakeParameterService:
    def __init__(self) -> None:
        self.created_drafts: list[ParameterSetCreate] = []

    async def create_draft(self, parameter_set: ParameterSetCreate) -> ParameterSet:
        self.created_drafts.append(parameter_set)
        return ParameterSet(
            id=1,
            name=parameter_set.name,
            device_type=parameter_set.device_type,
            version=1,
            status=ParameterStatus.DRAFT,
            source=parameter_set.source,
            created_by=parameter_set.created_by,
            note=parameter_set.note,
            created_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
        )

    async def submit(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        raise NotImplementedError

    async def approve(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        raise NotImplementedError

    async def reject(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        raise NotImplementedError

    async def activate(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        raise NotImplementedError

    async def get_latest(self, device_type: str) -> ParameterSetWithItems | None:
        raise NotImplementedError

    async def record_confirmation(self, **kwargs: Any) -> None:
        raise NotImplementedError


SAMPLE_PROFILE_REQUEST = {
    "feature_fields": ["temperature"],
    "target_fields": ["solder_joint_quality"],
}


@pytest.mark.asyncio
async def test_profile_returns_profiling_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/analysis/profile", json=SAMPLE_PROFILE_REQUEST)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["field"] == "temp"
    assert data[0]["mean"] == 180.0
    assert len(analysis_service.profile_called_with) == 1


@pytest.mark.asyncio
async def test_correlation_returns_correlation_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/correlation",
            json={"field_x": "a", "field_y": "b", "method": "pearson"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["field_x"] == "a"
    assert data["field_y"] == "b"
    assert data["coefficient"] == 0.9
    assert len(analysis_service.correlation_called_with) == 1


@pytest.mark.asyncio
async def test_importance_returns_importance_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/importance",
            json={"feature_fields": ["temp"], "target_field": "yield", "method": "random_forest"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["importances"] == {"temp": 0.8}
    assert data["method"] == "random_forest"
    assert len(analysis_service.importance_called_with) == 1


@pytest.mark.asyncio
async def test_regression_returns_regression_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/regression",
            json={"feature_fields": ["temp"], "target_field": "yield", "model_type": "linear"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["r_squared"] == 0.95
    assert data["rmse"] == 0.1
    assert data["model_type"] == "linear"
    assert len(analysis_service.regression_called_with) == 1


@pytest.mark.asyncio
async def test_recommendation_returns_recommendation_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/recommendation",
            json={
                "feature_fields": ["temp"],
                "target_field": "yield",
                "target_value": 90.0,
                "constraints": [],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_parameters"] == {"temp": 180}
    assert data["predicted_target"] == 90.0
    assert len(analysis_service.recommendation_called_with) == 1


@pytest.mark.asyncio
async def test_recommendation_submit_creates_draft() -> None:
    analysis_service = FakeAnalysisService()
    parameter_service = FakeParameterService()
    app = create_app(analysis_service=analysis_service, parameter_service=parameter_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/recommendation/submit",
            json={
                "name": "Optimized params",
                "device_type": "oven",
                "source": "analysis",
                "created_by": "system",
                "items": [
                    {"param_key": "temperature", "param_value": 180, "data_type": "number"},
                ],
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Optimized params"
    assert data["status"] == "draft"
    assert len(parameter_service.created_drafts) == 1


@pytest.mark.asyncio
async def test_analysis_error_returns_structured_error() -> None:
    analysis_service = FakeAnalysisService()
    analysis_service.fail_on = "profile"
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/analysis/profile", json=SAMPLE_PROFILE_REQUEST)

    assert response.status_code == 422
    error = response.json()
    assert error["code"] == "EMPTY_DATASET"
    assert error["message"] == "Dataset is empty"
    assert error["suggestion"] == "Add more data"


@pytest.mark.asyncio
async def test_spc_returns_spc_result() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/spc",
            json={"device_id": "D1", "field": "temperature"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["overview"]) == 1
    assert data["overview"][0]["field"] == "temperature"
    assert data["overview"][0]["cpk"] == 1.0
    assert data["i_chart"] is not None
    assert data["i_chart"]["mean"] == 200.0


@pytest.mark.asyncio
async def test_spc_overview_only() -> None:
    analysis_service = FakeAnalysisService()
    app = create_app(analysis_service=analysis_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analysis/spc",
            json={"device_id": "D1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["overview"]) == 1
    assert data["i_chart"] is None
