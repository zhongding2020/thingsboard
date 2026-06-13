from __future__ import annotations

from process_opt.analysis.correlation import compute_correlation
from process_opt.analysis.dataset import DatasetBuilder
from process_opt.analysis.importance import compute_importance
from process_opt.analysis.profiling import profile_dataset
from process_opt.analysis.recommendation import compute_recommendation
from process_opt.analysis.regression import fit_regression
from process_opt.analysis.schemas import (
    AnalysisDataset,
    AnalysisDatasetRequest,
    CorrelationRequest,
    CorrelationResult,
    ImportanceRequest,
    ImportanceResult,
    ProfilingResult,
    RecommendationRequest,
    RecommendationResult,
    RegressionRequest,
    RegressionResult,
    SpcRequest,
    SpcResult,
)
from process_opt.analysis.errors import AnalysisError


class AnalysisService:
    def __init__(self, dataset_builder: DatasetBuilder) -> None:
        self._builder = dataset_builder

    async def build_dataset(self, request: AnalysisDatasetRequest) -> AnalysisDataset:
        result = await self._builder.build(request)
        if isinstance(result, AnalysisError):
            raise result
        return result

    async def profile(self, dataset: AnalysisDataset) -> list[ProfilingResult]:
        return profile_dataset(dataset)

    async def profile_from_request(self, request: AnalysisDatasetRequest) -> list[ProfilingResult]:
        dataset = await self.build_dataset(request)
        return profile_dataset(dataset)

    async def correlation(self, request: CorrelationRequest) -> CorrelationResult:
        dataset_req = AnalysisDatasetRequest(
            feature_fields=[request.field_x],
            target_fields=[request.field_y],
        )
        result = await self._builder.build(dataset_req)
        if isinstance(result, AnalysisError):
            raise result
        results = compute_correlation(
            result,
            [request.field_x],
            [request.field_y],
            request.method,
        )
        return results[0]

    async def importance(self, request: ImportanceRequest) -> ImportanceResult:
        dataset_req = AnalysisDatasetRequest(
            feature_fields=request.feature_fields,
            target_fields=[request.target_field],
        )
        result = await self._builder.build(dataset_req)
        if isinstance(result, AnalysisError):
            raise result
        return compute_importance(
            result,
            request.feature_fields,
            request.target_field,
            request.method,
        )

    async def regression(self, request: RegressionRequest) -> RegressionResult:
        dataset_req = AnalysisDatasetRequest(
            feature_fields=request.feature_fields,
            target_fields=[request.target_field],
        )
        result = await self._builder.build(dataset_req)
        if isinstance(result, AnalysisError):
            raise result
        return fit_regression(
            result,
            request.feature_fields,
            request.target_field,
            request.model_type,
        )

    async def recommendation(self, request: RecommendationRequest) -> RecommendationResult:
        dataset_req = AnalysisDatasetRequest(
            feature_fields=request.feature_fields,
            target_fields=[request.target_field],
        )
        result = await self._builder.build(dataset_req)
        if isinstance(result, AnalysisError):
            raise result
        return compute_recommendation(result, request.feature_fields, request)

    async def spc(self, request: SpcRequest) -> SpcResult:
        from process_opt.analysis.spc import build_spc_result
        overview_req = AnalysisDatasetRequest(
            feature_fields=[],
            target_fields=[],
            max_samples=None,
            missing_strategy="mean",
        )
        overview_dataset = await self.build_dataset(overview_req)

        field = request.field
        if field is not None:
            field_req = AnalysisDatasetRequest(
                feature_fields=[field],
                target_fields=[],
                max_samples=None,
                missing_strategy="mean",
            )
            field_dataset = await self.build_dataset(field_req)
            if field not in {f for feat in field_dataset.features for f in feat}:
                existing = sorted({f for feat in overview_dataset.features for f in feat})
                raise AnalysisError(
                    code="FIELD_NOT_FOUND",
                    message=f"Field '{field}' not found in data",
                    suggestion=f"Available fields: {existing}",
                )
        else:
            field_dataset = overview_dataset

        return build_spc_result(
            overview_dataset=overview_dataset,
            field_dataset=field_dataset,
            field=field,
            usl=request.usl,
            lsl=request.lsl,
            target=request.target,
        )
