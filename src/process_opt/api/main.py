from datetime import datetime
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

from process_opt.analysis import AnalysisService
from process_opt.analysis.dataset import DatasetBuilder
from process_opt.analysis.schemas import AnalysisDataset, AnalysisDatasetRequest, CorrelationRequest, CorrelationResult, ImportanceRequest, ImportanceResult, ProfilingResult, RecommendationRequest, RecommendationResult, RegressionRequest, RegressionResult, SpcRequest, SpcResult
from process_opt.api.app import create_app
from process_opt.common.db import apply_sql_file, create_pool
from process_opt.common.repositories import DataRepository
from process_opt.common.settings import Settings
from process_opt.parameters.repository import ParameterRepository
from process_opt.parameters.schemas import ParameterSet, ParameterSetCreate, ParameterSetWithItems
from process_opt.parameters.service import ParameterService


class RepositoryProxy:
    def __init__(self) -> None:
        self.repository: DataRepository | None = None

    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None:
        if self.repository is None:
            raise RuntimeError("Repository is not initialized")
        return await self.repository.get_analysis_record(barcode)

    async def query_records(
        self,
        barcode: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if self.repository is None:
            raise RuntimeError("Repository is not initialized")
        return await self.repository.query_records(barcode, device_id, start_time, end_time, page, page_size)

    async def list_devices(self) -> list[str]:
        if self.repository is None:
            raise RuntimeError("Repository is not initialized")
        return await self.repository.list_devices()

    async def get_stats(self) -> dict[str, Any]:
        if self.repository is None:
            raise RuntimeError("Repository is not initialized")
        return await self.repository.get_stats()


class ParameterServiceProxy:
    def __init__(self) -> None:
        self._service: ParameterService | None = None

    async def create_draft(self, parameter_set: ParameterSetCreate) -> ParameterSet:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.create_draft(parameter_set)

    async def submit(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.submit(set_id, actor, note)

    async def approve(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.approve(set_id, actor, note)

    async def reject(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.reject(set_id, actor, note)

    async def activate(self, set_id: int, actor: str, note: str | None = None) -> ParameterSet:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.activate(set_id, actor, note)

    async def get_latest(self, device_type: str) -> ParameterSetWithItems | None:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.get_latest(device_type)

    async def record_confirmation(self, **kwargs: Any) -> None:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        await self._service.record_confirmation(**kwargs)


class AnalysisServiceProxy:
    def __init__(self) -> None:
        self._service: AnalysisService | None = None

    async def profile(self, dataset: AnalysisDataset) -> list[ProfilingResult]:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.profile(dataset)

    async def profile_from_request(self, request: AnalysisDatasetRequest) -> list[ProfilingResult]:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.profile_from_request(request)

    async def correlation(self, request: CorrelationRequest) -> CorrelationResult:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.correlation(request)

    async def importance(self, request: ImportanceRequest) -> ImportanceResult:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.importance(request)

    async def regression(self, request: RegressionRequest) -> RegressionResult:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.regression(request)

    async def recommendation(self, request: RecommendationRequest) -> RecommendationResult:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.recommendation(request)

    async def spc(self, request: SpcRequest) -> SpcResult:
        if self._service is None:
            raise RuntimeError("AnalysisService not initialized")
        return await self._service.spc(request)


def create_api_app_from_settings() -> FastAPI:
    settings = Settings()
    repository_proxy = RepositoryProxy()
    parameter_service_proxy = ParameterServiceProxy()
    analysis_service_proxy = AnalysisServiceProxy()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = await create_pool(settings.postgres_dsn)
        migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "db" / "migrations"
        for fpath in sorted(migrations_dir.glob("*.sql")):
            await apply_sql_file(pool, fpath)
        repository = DataRepository(pool)
        parameter_repo = ParameterRepository(pool)
        parameter_service = ParameterService(parameter_repo)
        dataset_builder = DatasetBuilder(pool)
        analysis_service = AnalysisService(dataset_builder)
        app.state.pool = pool
        app.state.repository = repository
        repository_proxy.repository = repository
        parameter_service_proxy._service = parameter_service
        analysis_service_proxy._service = analysis_service
        try:
            yield
        finally:
            repository_proxy.repository = None
            parameter_service_proxy._service = None
            analysis_service_proxy._service = None
            await pool.close()

    app = create_app(repository_proxy, parameter_service_proxy, analysis_service_proxy)
    app.router.lifespan_context = lifespan
    return app


def main() -> None:
    uvicorn.run(create_api_app_from_settings(), host="0.0.0.0", port=8000)
