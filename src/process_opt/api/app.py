import logging
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
        product_model: str | None = None,
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


class LineDeviceRepositoryProtocol(Protocol):
    async def list_lines(self) -> list[dict[str, Any]]: ...
    async def get_line(self, line_id: str) -> dict[str, Any] | None: ...
    async def create_line(self, name: str, responsible: str, location: str | None) -> dict[str, Any]: ...
    async def update_line(self, line_id: str, name: str | None, responsible: str | None, location: str | None) -> dict[str, Any] | None: ...
    async def delete_line(self, line_id: str) -> bool: ...
    async def list_devices(self, line_id: str | None = None) -> list[dict[str, Any]]: ...
    async def get_device(self, device_id: str) -> dict[str, Any] | None: ...
    async def update_device(self, device_id: str, name: str | None, type_: str | None, icon: str | None, description: str | None, line_id: str | None) -> dict[str, Any] | None: ...
    async def delete_device(self, device_id: str) -> bool: ...
    async def get_devices_by_line(self, line_id: str) -> list[str]: ...
    async def reorder_devices(self, line_id: str, device_ids: list[str]) -> None: ...


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


logger = logging.getLogger(__name__)


def create_app(
    repository: AnalysisRepository | None = None,
    parameter_service: ParameterService | None = None,
    analysis_service: AnalysisService | None = None,
    line_device_repo: LineDeviceRepositoryProtocol | None = None,
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
            product_model: str | None = None,
            page: int = 1,
            page_size: int = 20,
        ) -> Any:
            return await repository.query_records(
                barcode, device_id, start_time, end_time, product_model, page, page_size
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

    if line_device_repo is not None:

        @app.get("/api/v1/lines")
        async def list_lines_route() -> Any:
            return await line_device_repo.list_lines()

        @app.get("/api/v1/lines/{line_id}")
        async def get_line_route(line_id: str) -> Any:
            line = await line_device_repo.get_line(line_id)
            if line is None:
                raise HTTPException(status_code=404, detail="Line not found")
            devices = await line_device_repo.list_devices(line_id=line_id)
            line["devices"] = devices
            return line

        @app.post("/api/v1/lines", status_code=status.HTTP_201_CREATED)
        async def create_line_route(body: dict[str, Any]) -> Any:
            from process_opt.analysis.line_schemas import LineCreate
            lc = LineCreate(**body)
            return await line_device_repo.create_line(lc.name, lc.responsible, lc.location)

        @app.put("/api/v1/lines/{line_id}")
        async def update_line_route(line_id: str, body: dict[str, Any]) -> Any:
            from process_opt.analysis.line_schemas import LineUpdate
            lu = LineUpdate(**body)
            result = await line_device_repo.update_line(line_id, lu.name, lu.responsible, lu.location)
            if result is None:
                raise HTTPException(status_code=404, detail="Line not found")
            return result

        @app.delete("/api/v1/lines/{line_id}")
        async def delete_line_route(line_id: str) -> Response:
            ok = await line_device_repo.delete_line(line_id)
            if not ok:
                raise HTTPException(status_code=409, detail="Line has assigned devices")
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        @app.get("/api/v1/devices")
        async def list_devices_route(line_id: str | None = None) -> Any:
            return await line_device_repo.list_devices(line_id=line_id)

        @app.get("/api/v1/devices/{device_id}")
        async def get_device_route(device_id: str) -> Any:
            device = await line_device_repo.get_device(device_id)
            if device is None:
                raise HTTPException(status_code=404, detail="Device not found")
            return device

        @app.put("/api/v1/devices/{device_id}")
        async def update_device_route(device_id: str, body: dict[str, Any]) -> Any:
            from process_opt.analysis.line_schemas import DeviceUpdate
            du = DeviceUpdate(**body)
            result = await line_device_repo.update_device(
                device_id, du.name, du.type, du.icon, du.description, du.line_id,
            )
            if result is None:
                raise HTTPException(status_code=404, detail="Device not found")
            return result

        @app.delete("/api/v1/devices/{device_id}")
        async def delete_device_route(device_id: str) -> Response:
            ok = await line_device_repo.delete_device(device_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Device not found")
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        @app.put("/api/v1/lines/{line_id}/reorder")
        async def reorder_devices_route(line_id: str, body: dict[str, Any]) -> Response:
            device_ids = body.get("device_ids", [])
            if not isinstance(device_ids, list) or not device_ids:
                raise HTTPException(status_code=400, detail="device_ids list is required")
            await line_device_repo.reorder_devices(line_id, device_ids)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        @app.get("/api/v1/lines/{line_id}/monitor")
        async def line_monitor_route(line_id: str) -> Any:
            line = await line_device_repo.get_line(line_id)
            if line is None:
                raise HTTPException(status_code=404, detail="Line not found")
            devices = await line_device_repo.list_devices(line_id=line_id)

            device_summaries: list[dict[str, Any]] = []
            normal = abnormal = marginal = no_spec = 0

            for device in devices:
                from process_opt.analysis.schemas import SpcRequest
                if analysis_service is None:
                    continue
                try:
                    result = await analysis_service.spc(SpcRequest(
                        device_id=device["id"],
                    ))
                except Exception as exc:
                    logger.warning("SPC analysis failed for device %s: %s", device["id"], exc)
                    continue
                if not result.overview:
                    continue
                statuses = [ov.status for ov in result.overview]
                if "abnormal" in statuses:
                    dev_status = "abnormal"
                elif "marginal" in statuses:
                    dev_status = "marginal"
                elif "no_spec" in statuses:
                    dev_status = "no_spec"
                else:
                    dev_status = "normal"
                cpks = [ov.cpk for ov in result.overview if ov.cpk is not None]
                device_summaries.append({
                    "device_id": device["id"],
                    "device_name": device["name"],
                    "type": device["type"],
                    "status": dev_status,
                    "worst_cpk": round(min(cpks), 2) if cpks else None,
                    "param_count": len(result.overview),
                    "outlier_total": sum(ov.outlier_count for ov in result.overview),
                })
                if dev_status == "abnormal":
                    abnormal += 1
                elif dev_status == "marginal":
                    marginal += 1
                elif dev_status == "no_spec":
                    no_spec += 1
                else:
                    normal += 1

            if abnormal > 0:
                line_status = "abnormal"
            elif marginal > 0:
                line_status = "marginal"
            elif no_spec > 0:
                line_status = "no_spec"
            elif normal > 0:
                line_status = "normal"
            else:
                line_status = "empty"

            return {
                "line": line,
                "summary": {
                    "device_count": len(devices),
                    "normal_count": normal,
                    "abnormal_count": abnormal,
                    "marginal_count": marginal,
                    "no_spec_count": no_spec,
                    "status": line_status,
                },
                "devices": device_summaries,
            }

    if analysis_service is not None:

        @app.post("/api/v1/analysis/profile")
        async def profile_route(body: AnalysisDatasetRequest) -> list[ProfilingResult]:
            if body.dataset_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.profiling import profile_dataset
                ds = get_dataset(body.dataset_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                return profile_dataset(ds)
            return await analysis_service.profile_from_request(body)

        @app.post("/api/v1/analysis/correlation")
        async def correlation_route(body: CorrelationRequest) -> Any:
            if body.dataset_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.correlation import compute_correlation
                ds = get_dataset(body.dataset_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                if body.field_x and body.field_y:
                    results = compute_correlation(ds, [body.field_x], [body.field_y], body.method)
                    return results[0]
                feature_cols = sorted({k for f in ds.features for k in f})
                target_cols = sorted({k for t in ds.targets for k in t})
                return compute_correlation(ds, feature_cols, target_cols, body.method)
            return await analysis_service.correlation(body)

        @app.post("/api/v1/analysis/importance")
        async def importance_route(body: ImportanceRequest) -> ImportanceResult:
            return await analysis_service.importance(body)

        @app.post("/api/v1/analysis/regression")
        async def regression_route(body: RegressionRequest) -> Any:
            if body.dataset_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.regression import fit_regression
                ds = get_dataset(body.dataset_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                return fit_regression(ds, body.feature_fields, body.target_field, body.model_type)
            return await analysis_service.regression(body)

        @app.post("/api/v1/analysis/recommendation")
        async def recommendation_route(body: RecommendationRequest) -> Any:
            if body.dataset_id:
                from process_opt.analysis.excel import get_dataset
                from process_opt.analysis.recommendation import compute_recommendation
                ds = get_dataset(body.dataset_id)
                if ds is None:
                    raise HTTPException(status_code=404, detail="Dataset not found or expired")
                return compute_recommendation(ds, body.feature_fields, body)
            return await analysis_service.recommendation(body)

        @app.post("/api/v1/analysis/spc")
        async def spc_route(body: SpcRequest) -> SpcResult:
            return await analysis_service.spc(body)

        @app.post("/api/v1/analysis/dataset/upload")
        async def dataset_upload(file: UploadFile) -> Any:
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

        @app.get("/api/v1/analysis/dataset/{dataset_id}/preview")
        async def dataset_preview_route(
            dataset_id: str,
            page: int = 1,
            size: int = 50,
        ) -> Any:
            from process_opt.analysis.excel import get_dataset
            ds = get_dataset(dataset_id)
            if ds is None:
                raise HTTPException(status_code=404, detail="Dataset not found or expired")
            total = len(ds.features)
            start = (page - 1) * size
            end = min(start + size, total)

            feature_names = sorted({k for f in ds.features for k in f})
            target_names = sorted({k for t in ds.targets for k in t})

            rows: list[dict[str, Any]] = []
            for i in range(start, end):
                row: dict[str, Any] = {}
                if i < len(ds.metadata):
                    row["_barcode"] = ds.metadata[i].get("barcode", "")
                for fn in feature_names:
                    row[fn] = ds.features[i].get(fn) if i < len(ds.features) else None
                for tn in target_names:
                    row[tn] = ds.targets[i].get(tn) if i < len(ds.targets) else None
                rows.append(row)

            field_meta = {
                "features": [
                    {
                        "name": fn,
                        "type": "numeric",
                        "min": ds.field_summary.get(fn, {}).get("min"),
                        "max": ds.field_summary.get(fn, {}).get("max"),
                    }
                    for fn in feature_names
                ],
                "targets": [
                    {
                        "name": tn,
                        "type": "pass_fail",
                    }
                    for tn in target_names
                ],
            }
            return {
                "rows": rows,
                "total": total,
                "page": page,
                "size": size,
                "fields": field_meta,
            }

        @app.post("/api/v1/analysis/dataset/query")
        async def dataset_query_route(body: dict[str, Any]) -> Any:
            from process_opt.analysis.dataset import DatasetBuilder
            from process_opt.analysis.excel import get_dataset
            builder = DatasetBuilder(app.state.pool)
            device_id = body.get("device_id", "")
            if not device_id:
                raise HTTPException(status_code=400, detail="device_id is required")
            since_raw = body.get("since")
            since: datetime | None = None
            if since_raw:
                try:
                    since = datetime.fromisoformat(since_raw)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid since format, use ISO 8601")
            ds_id = await builder.build_to_dataset_id(device_id, since=since)
            ds = get_dataset(ds_id)
            feature_fields = sorted({k for f in ds.features for k in f}) if ds else []
            target_fields = sorted({k for t in ds.targets for k in t}) if ds else []
            return {
                "dataset_id": ds_id,
                "fields": {"features": feature_fields, "targets": target_fields},
                "sample_count": ds.sample_count if ds else 0,
            }

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
