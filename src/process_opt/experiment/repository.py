from datetime import datetime
import json

from asyncpg import Pool
from pydantic import BaseModel, Field


class ExperimentPlanCreate(BaseModel):
    name: str
    process_type: str = "adhesive_curing"
    method: str
    factors: list[dict]
    design_runs: list[dict]
    response_name: str = "response"
    created_by: str = "system"


class ExperimentPlan(BaseModel):
    id: int
    name: str
    process_type: str
    method: str
    factors: list[dict]
    design_runs: list[dict]
    response_name: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class ExperimentResultCreate(BaseModel):
    run_order: int
    response_value: float | None = None
    notes: str | None = None


class ExperimentResult(BaseModel):
    id: int
    plan_id: int
    run_order: int
    response_value: float | None
    notes: str | None
    recorded_at: datetime


class ExperimentPlanWithResults(ExperimentPlan):
    results: list[ExperimentResult] = []


class ExperimentRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def create_plan(self, data: ExperimentPlanCreate) -> ExperimentPlan:
        row = await self._pool.fetchrow(
            """INSERT INTO experiment_plans (name, process_type, method, factors, design_runs, response_name, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
            data.name, data.process_type, data.method,
            data.factors, data.design_runs,
            data.response_name, data.created_by,
        )
        return self._row_to_plan(row)

    async def list_plans(self, limit: int = 20) -> list[ExperimentPlan]:
        rows = await self._pool.fetch(
            "SELECT * FROM experiment_plans ORDER BY created_at DESC LIMIT $1", limit,
        )
        return [self._row_to_plan(r) for r in rows]

    async def get_plan(self, plan_id: int) -> ExperimentPlanWithResults | None:
        import json as _json

        plan_row = await self._pool.fetchrow(
            "SELECT * FROM experiment_plans WHERE id=$1", plan_id,
        )
        if not plan_row:
            return None
        plan = self._row_to_plan(plan_row)
        result_rows = await self._pool.fetch(
            "SELECT * FROM experiment_results WHERE plan_id=$1 ORDER BY run_order", plan_id,
        )
        results = [ExperimentResult(**dict(r)) for r in result_rows]
        return ExperimentPlanWithResults(**plan.model_dump(), results=results)

    async def record_result(self, plan_id: int, data: ExperimentResultCreate) -> ExperimentResult:
        row = await self._pool.fetchrow(
            """INSERT INTO experiment_results (plan_id, run_order, response_value, notes)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (plan_id, run_order) DO UPDATE
               SET response_value=$3, notes=$4, recorded_at=NOW()
               RETURNING *""",
            plan_id, data.run_order, data.response_value, data.notes,
        )
        await self._update_plan_status(plan_id)
        return ExperimentResult(**dict(row))

    async def batch_record_results(
        self, plan_id: int, results: list[ExperimentResultCreate],
    ) -> list[ExperimentResult]:
        recorded: list[ExperimentResult] = []
        for r in results:
            recorded.append(await self.record_result(plan_id, r))
        return recorded

    async def update_plan_status(self, plan_id: int, status: str) -> None:
        await self._pool.execute(
            "UPDATE experiment_plans SET status=$1, updated_at=NOW() WHERE id=$2",
            status, plan_id,
        )

    async def _update_plan_status(self, plan_id: int) -> None:
        total_runs = await self._pool.fetchval(
            "SELECT jsonb_array_length(design_runs) FROM experiment_plans WHERE id=$1", plan_id,
        )
        recorded = await self._pool.fetchval(
            "SELECT COUNT(*) FROM experiment_results WHERE plan_id=$1 AND response_value IS NOT NULL", plan_id,
        )
        if recorded and total_runs:
            if recorded >= total_runs:
                await self.update_plan_status(plan_id, "completed")
            elif recorded > 0:
                await self.update_plan_status(plan_id, "in_progress")

    def _row_to_plan(self, row: any) -> ExperimentPlan:
        d = dict(row)
        for key in ("factors", "design_runs"):
            val = d.get(key)
            if isinstance(val, str):
                d[key] = json.loads(val)
        return ExperimentPlan(**d)
