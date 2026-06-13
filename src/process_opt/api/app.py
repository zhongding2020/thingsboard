from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from process_opt.analysis.errors import AnalysisError
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
from process_opt.parameters.errors import ParameterError
from process_opt.parameters.schemas import (
    ParameterConfirmationCreate,
    ParameterSet,
    ParameterSetCreate,
    ParameterSetWithItems,
)


class AnalysisRepository(Protocol):
    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None: ...
    async def query_records(
        self,
        barcode: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]: ...
    async def list_devices(self) -> list[str]: ...
    async def get_stats(self) -> dict[str, Any]: ...


class ParameterService(Protocol):
    async def create_draft(self, parameter_set: ParameterSetCreate) -> ParameterSet: ...
    async def submit(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet: ...
    async def approve(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet: ...
    async def reject(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet: ...
    async def activate(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet: ...
    async def get_latest(self, device_type: str) -> ParameterSetWithItems | None: ...
    async def record_confirmation(self, **kwargs: Any) -> None: ...


class AnalysisService(Protocol):
    async def profile(self, dataset: AnalysisDataset) -> list[ProfilingResult]: ...
    async def correlation(self, request: CorrelationRequest) -> CorrelationResult: ...
    async def importance(self, request: ImportanceRequest) -> ImportanceResult: ...
    async def regression(self, request: RegressionRequest) -> RegressionResult: ...
    async def recommendation(self, request: RecommendationRequest) -> RecommendationResult: ...
    async def spc(self, request: SpcRequest) -> SpcResult: ...


class StatusTransitionRequest(BaseModel):
    actor: str = Field(min_length=1)
    note: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    suggestion: str


_SUGGESTIONS: dict[str, str] = {
    "NOT_FOUND": "Check the set_id parameter and try again.",
    "INVALID_TRANSITION": "Check allowed transitions: draft->proposed, proposed->approved, proposed->rejected, approved->active.",
}


def _error_response(code: str, message: str) -> ErrorResponse:
    return ErrorResponse(
        code=code,
        message=message,
        suggestion=_SUGGESTIONS.get(code, "An unexpected error occurred."),
    )


def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisService | None = None,
) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> Response:
        error = _error_response("NOT_FOUND", str(exc))
        return Response(
            content=error.model_dump_json(),
            status_code=status.HTTP_404_NOT_FOUND,
            media_type="application/json",
        )

    @app.exception_handler(ParameterError)
    async def parameter_error_handler(request: Request, exc: ParameterError) -> Response:
        error = _error_response(exc.code, exc.message)
        return Response(
            content=error.model_dump_json(),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            media_type="application/json",
        )

    @app.exception_handler(AnalysisError)
    async def analysis_error_handler(request: Request, exc: AnalysisError) -> Response:
        error = ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            suggestion=exc.suggestion or "An unexpected error occurred.",
        )
        return Response(
            content=error.model_dump_json(),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            media_type="application/json",
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if repository is not None:

        @app.get("/api/v1/analysis/records")
        async def query_records_route(
            barcode: str | None = None,
            device_id: str | None = None,
            start_time: datetime | None = None,
            end_time: datetime | None = None,
            page: int = 1,
            page_size: int = 20,
        ) -> Any:
            return await repository.query_records(
                barcode, device_id, start_time, end_time, page, page_size
            )

        @app.get("/api/v1/analysis/records/{barcode}")
        async def get_analysis_record(barcode: str) -> Any:
            record = await repository.get_analysis_record(barcode)
            if record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Analysis record not found"
                )
            return jsonable_encoder(record)

        @app.get("/api/v1/analysis/devices")
        async def list_devices_route() -> Any:
            return await repository.list_devices()

        @app.get("/api/v1/analysis/stats")
        async def stats_route() -> Any:
            return await repository.get_stats()

    if parameter_service is not None:

        @app.post("/api/v1/parameters/sets", status_code=status.HTTP_201_CREATED)
        async def create_draft(body: ParameterSetCreate) -> ParameterSet:
            return await parameter_service.create_draft(body)

        @app.post("/api/v1/parameters/sets/{set_id}/submit")
        async def submit_set(set_id: int, body: StatusTransitionRequest) -> ParameterSet:
            return await parameter_service.submit(set_id, body.actor, body.note)

        @app.post("/api/v1/parameters/sets/{set_id}/approve")
        async def approve_set(set_id: int, body: StatusTransitionRequest) -> ParameterSet:
            return await parameter_service.approve(set_id, body.actor, body.note)

        @app.post("/api/v1/parameters/sets/{set_id}/reject")
        async def reject_set(set_id: int, body: StatusTransitionRequest) -> ParameterSet:
            return await parameter_service.reject(set_id, body.actor, body.note)

        @app.post("/api/v1/parameters/sets/{set_id}/activate")
        async def activate_set(set_id: int, body: StatusTransitionRequest) -> ParameterSet:
            return await parameter_service.activate(set_id, body.actor, body.note)

        @app.get("/api/v1/parameters/latest")
        async def get_latest_parameters(
            device_type: str,
            device_id: str | None = None,
        ) -> ParameterSetWithItems:
            result = await parameter_service.get_latest(device_type)
            if result is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active parameter set found",
                )
            return result

        @app.post("/api/v1/parameters/confirmations", status_code=status.HTTP_204_NO_CONTENT)
        async def record_confirmation(body: ParameterConfirmationCreate) -> Response:
            await parameter_service.record_confirmation(**body.model_dump())
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    if analysis_service is not None:

        @app.post("/api/v1/analysis/profile")
        async def profile_route(body: AnalysisDatasetRequest) -> list[ProfilingResult]:
            return await analysis_service.profile_from_request(body)

        @app.post("/api/v1/analysis/correlation")
        async def correlation_route(body: CorrelationRequest) -> CorrelationResult:
            return await analysis_service.correlation(body)

        @app.post("/api/v1/analysis/importance")
        async def importance_route(body: ImportanceRequest) -> ImportanceResult:
            return await analysis_service.importance(body)

        @app.post("/api/v1/analysis/regression")
        async def regression_route(body: RegressionRequest) -> RegressionResult:
            return await analysis_service.regression(body)

        @app.post("/api/v1/analysis/recommendation")
        async def recommendation_route(body: RecommendationRequest) -> RecommendationResult:
            return await analysis_service.recommendation(body)

        @app.post("/api/v1/analysis/spc")
        async def spc_route(body: SpcRequest) -> SpcResult:
            return await analysis_service.spc(body)

        @app.post("/api/v1/analysis/excel/upload")
        async def excel_upload(file: UploadFile) -> Any:
            from process_opt.analysis.excel import parse_excel, save_dataset
            content = await file.read()
            ds = parse_excel(content)
            ds_id = save_dataset(ds)
            feature_fields = sorted({k for f in ds.features for k in f})
            target_fields = sorted({k for t in ds.targets for k in t})
            return {
                "dataset_id": ds_id,
                "fields": {"features": feature_fields, "targets": target_fields},
                "sample_count": ds.sample_count,
            }

        @app.post("/api/v1/analysis/excel/profile")
        async def excel_profile_route(body: dict[str, Any]) -> list[ProfilingResult]:
            from process_opt.analysis.excel import get_dataset
            from process_opt.analysis.profiling import profile_dataset
            ds = get_dataset(body.get("dataset_id", ""))
            if ds is None:
                raise HTTPException(status_code=404, detail="Dataset not found or expired")
            return profile_dataset(ds)

        @app.post("/api/v1/analysis/excel/correlation")
        async def excel_correlation_route(body: dict[str, Any]) -> CorrelationResult:
            from process_opt.analysis.excel import get_dataset
            from process_opt.analysis.correlation import compute_correlation
            ds = get_dataset(body.get("dataset_id", ""))
            if ds is None:
                raise HTTPException(status_code=404, detail="Dataset not found or expired")
            results = compute_correlation(ds, [body["field_x"]], [body["field_y"]], body.get("method", "pearson"))
            return results[0]

        @app.post("/api/v1/analysis/excel/regression")
        async def excel_regression_route(body: dict[str, Any]) -> RegressionResult:
            from process_opt.analysis.excel import get_dataset
            from process_opt.analysis.regression import fit_regression
            ds = get_dataset(body.get("dataset_id", ""))
            if ds is None:
                raise HTTPException(status_code=404, detail="Dataset not found or expired")
            req = RegressionRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
            return fit_regression(ds, req.feature_fields, req.target_field, req.model_type)

        @app.post("/api/v1/analysis/excel/recommendation")
        async def excel_recommendation_route(body: dict[str, Any]) -> RecommendationResult:
            from process_opt.analysis.excel import get_dataset
            from process_opt.analysis.recommendation import compute_recommendation
            ds = get_dataset(body.get("dataset_id", ""))
            if ds is None:
                raise HTTPException(status_code=404, detail="Dataset not found or expired")
            req = RecommendationRequest(**{k: v for k, v in body.items() if k != "dataset_id"})
            return compute_recommendation(ds, req.feature_fields, req)

        if parameter_service is not None:

            @app.post(
                "/api/v1/analysis/recommendation/submit",
                status_code=status.HTTP_201_CREATED,
            )
            async def recommendation_submit_route(body: ParameterSetCreate) -> ParameterSet:
                return await parameter_service.create_draft(body)

    _web_dist = (
        candidate
        for candidate in [
            Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist",
            Path("/app/web/dist"),
            Path("web/dist"),
        ]
        if candidate.is_dir()
    )
    web_dist = next(_web_dist, None)
    if web_dist is not None:
        _MIME_TYPES: dict[str, str] = {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".md": "text/markdown",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
            ".map": "application/json",
        }

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> Response:
            if full_path.startswith("api/") or full_path == "health":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            target = web_dist / (full_path or "index.html")
            if not target.exists() or not target.is_file():
                target = web_dist / "index.html"
            media_type = _MIME_TYPES.get(target.suffix, "application/octet-stream")
            return Response(content=target.read_bytes(), media_type=media_type)

    return app
