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
from process_opt.common.repositories import DataRepository, LineDeviceRepository
from process_opt.common.settings import Settings
from process_opt.parameters.repository import ParameterRepository
from process_opt.parameters.schemas import ParameterSet, ParameterSetCreate, ParameterSetWithItems
from process_opt.parameters.service import ParameterService
try:
    from process_opt.container_pool.manager import ContainerPoolManager
    from process_opt.container_pool.proxy import ContainerPoolProxy
    _HAS_CONTAINER_POOL = True
except ImportError:
    ContainerPoolManager = None  # type: ignore
    ContainerPoolProxy = None  # type: ignore
    _HAS_CONTAINER_POOL = False
from process_opt.agent.tools.analysis_tools import create_analysis_tools
from process_opt.agent.tools.system_tools import create_system_tools
from process_opt.agent.tools.parameter_tools import create_parameter_tools
from process_opt.agent.tools.experiment_tools import create_experiment_tools
from process_opt.agent.graph import SessionManager, build_graph
from process_opt.knowledge.loader import KnowledgeLoader
from process_opt.experiment.repository import ExperimentRepository


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
        station_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        product_model: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if self.repository is None:
            raise RuntimeError("Repository is not initialized")
        return await self.repository.query_records(barcode, device_id, station_id, start_time, end_time, product_model, page, page_size)

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

    async def list_sets(self) -> list[ParameterSet]:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.list_sets()

    async def get_set_with_items(self, set_id: int) -> ParameterSetWithItems | None:
        if self._service is None:
            raise RuntimeError("ParameterService not initialized")
        return await self._service.get_set_with_items(set_id)

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


class LineDeviceRepositoryProxy:
    def __init__(self) -> None:
        self._repo: LineDeviceRepository | None = None

    async def list_lines(self) -> list[dict[str, Any]]:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.list_lines()

    async def get_line(self, line_id: str) -> dict[str, Any] | None:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.get_line(line_id)

    async def create_line(self, name: str, responsible: str, location: str | None) -> dict[str, Any]:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.create_line(name, responsible, location)

    async def update_line(self, line_id: str, name: str | None, responsible: str | None, location: str | None) -> dict[str, Any] | None:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.update_line(line_id, name, responsible, location)

    async def delete_line(self, line_id: str) -> bool:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.delete_line(line_id)

    async def list_devices(self, line_id: str | None = None) -> list[dict[str, Any]]:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.list_devices(line_id)

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.get_device(device_id)

    async def update_device(self, device_id: str, name: str | None, type_: str | None, icon: str | None, description: str | None, line_id: str | None) -> dict[str, Any] | None:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.update_device(device_id, name, type_, icon, description, line_id)

    async def delete_device(self, device_id: str) -> bool:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.delete_device(device_id)

    async def get_devices_by_line(self, line_id: str) -> list[str]:
        if self._repo is None:
            raise RuntimeError("LineDeviceRepository not initialized")
        return await self._repo.get_devices_by_line(line_id)


class ExperimentRepositoryProxy:
    def __init__(self) -> None:
        self._repo: Any = None

    async def create_plan(self, data: Any) -> Any:
        return await self._repo.create_plan(data)

    async def list_plans(self, limit: int = 20) -> list:
        return await self._repo.list_plans(limit)

    async def get_plan(self, plan_id: int) -> Any:
        return await self._repo.get_plan(plan_id)

    async def record_result(self, plan_id: int, data: Any) -> Any:
        return await self._repo.record_result(plan_id, data)

    async def batch_record_results(self, plan_id: int, results: list) -> list:
        return await self._repo.batch_record_results(plan_id, results)

    async def update_plan_status(self, plan_id: int, status: str) -> None:
        await self._repo.update_plan_status(plan_id, status)


def create_api_app_from_settings() -> FastAPI:
    settings = Settings()
    repository_proxy = RepositoryProxy()
    parameter_service_proxy = ParameterServiceProxy()
    analysis_service_proxy = AnalysisServiceProxy()
    line_device_repo_proxy = LineDeviceRepositoryProxy()
    container_pool_proxy = ContainerPoolProxy() if _HAS_CONTAINER_POOL else None
    experiment_repo_proxy = ExperimentRepositoryProxy()

    from langchain_openai import ChatOpenAI

    knowledge_loader = KnowledgeLoader()
    session_manager = SessionManager(ttl_seconds=settings.agent_session_ttl)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = await create_pool(settings.postgres_dsn)
        migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "db" / "migrations"
        for fpath in sorted(migrations_dir.glob("*.sql")):
            await apply_sql_file(pool, fpath)
        repository = DataRepository(pool)
        line_device_repo = LineDeviceRepository(pool)
        parameter_repo = ParameterRepository(pool)
        parameter_service = ParameterService(parameter_repo)
        dataset_builder = DatasetBuilder(pool)
        analysis_service = AnalysisService(dataset_builder)
        experiment_repo = ExperimentRepository(pool)
        experiment_repo_proxy._repo = experiment_repo
        if _HAS_CONTAINER_POOL:
            manager = ContainerPoolManager(settings)
            container_pool_proxy.set_manager(manager)
            await manager.start()
        app.state.pool = pool
        app.state.repository = repository
        repository_proxy.repository = repository
        line_device_repo_proxy._repo = line_device_repo
        parameter_service_proxy._service = parameter_service
        analysis_service_proxy._service = analysis_service
        try:
            yield
        finally:
            if _HAS_CONTAINER_POOL:
                await manager.stop()
                container_pool_proxy.reset()
            repository_proxy.repository = None
            line_device_repo_proxy._repo = None
            parameter_service_proxy._service = None
            analysis_service_proxy._service = None
            experiment_repo_proxy._repo = None
            await pool.close()

    tools = (
        create_analysis_tools(
            repository_proxy, analysis_service_proxy, parameter_service_proxy,
            knowledge_loader, experiment_repo_proxy,
        ) +
        create_system_tools(line_device_repo_proxy, analysis_service_proxy) +
        create_parameter_tools(parameter_service_proxy) +
        create_experiment_tools(experiment_repo_proxy)
    )
    llm = ChatOpenAI(
        model=settings.agent_model,
        base_url=settings.agent_api_base,
        api_key=settings.agent_api_key,
        temperature=settings.agent_temperature,
        streaming=True,
    )
    llm_with_tools = llm.bind_tools(tools)
    agent_graph = build_graph(llm, llm_with_tools, tools, knowledge_loader)

    app = create_app(
        repository=repository_proxy,
        parameter_service=parameter_service_proxy,
        analysis_service=analysis_service_proxy,
        line_device_repo=line_device_repo_proxy,
        container_pool=container_pool_proxy,
        agent_graph=agent_graph,
        session_manager=session_manager,
        knowledge_loader=knowledge_loader,
        experiment_repo=experiment_repo_proxy,
        suggestion_llm=llm,
    )
    app.router.lifespan_context = lifespan
    return app


def main() -> None:
    uvicorn.run(create_api_app_from_settings(), host="0.0.0.0", port=8000)
