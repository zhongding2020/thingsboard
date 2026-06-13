from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from pydantic import ValidationError

from process_opt.analysis.errors import (
    ANALYSIS_ERROR_CODES,
    AnalysisError,
)
from process_opt.analysis.schemas import (
    AnalysisDataset,
    AnalysisDatasetRequest,
    Constraint,
    CorrelationRequest,
    CorrelationResult,
    ImportanceRequest,
    ImportanceResult,
    ProfilingResult,
    RecommendationRequest,
    RecommendationResult,
    RegressionRequest,
    RegressionResult,
)
from process_opt.common.db import apply_sql_file, create_pool


# ---------------------------------------------------------------------------
# AnalysisError tests
# ---------------------------------------------------------------------------

class TestAnalysisError:
    def test_has_code_message_details_suggestion(self) -> None:
        err = AnalysisError(
            code="TEST_ERROR",
            message="something went wrong",
            details={"field": "x"},
            suggestion="try again",
        )
        assert err.code == "TEST_ERROR"
        assert err.message == "something went wrong"
        assert err.details == {"field": "x"}
        assert err.suggestion == "try again"

    def test_defaults_details_and_suggestion_to_none(self) -> None:
        err = AnalysisError(code="ERR", message="msg")
        assert err.details is None
        assert err.suggestion is None

    def test_error_code_constants_are_defined(self) -> None:
        expected = {
            "EMPTY_DATASET",
            "INSUFFICIENT_SAMPLES",
            "FIELD_NOT_FOUND",
            "NON_NUMERIC_FIELD",
            "TOO_MANY_SAMPLES",
            "SEARCH_SPACE_TOO_LARGE",
            "MODEL_FIT_FAILED",
            "INVALID_CONSTRAINT",
        }
        assert ANALYSIS_ERROR_CODES.keys() == expected

    def test_is_instance_of_exception(self) -> None:
        err = AnalysisError(code="X", message="y")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestAnalysisDatasetRequest:
    def test_accepts_required_fields(self) -> None:
        req = AnalysisDatasetRequest(
            feature_fields=["temperature"],
            target_fields=["diameter"],
        )
        assert req.feature_fields == ["temperature"]
        assert req.target_fields == ["diameter"]
        assert req.missing_strategy == "drop_row"
        assert req.max_samples is None

    def test_accepts_all_fields(self) -> None:
        req = AnalysisDatasetRequest(
            feature_fields=["a"],
            target_fields=["b"],
            missing_strategy="mean",
            max_samples=100,
        )
        assert req.missing_strategy == "mean"
        assert req.max_samples == 100

    def test_accepts_empty_feature_fields(self) -> None:
        req = AnalysisDatasetRequest(feature_fields=[], target_fields=["diameter"])
        assert req.feature_fields == []

    def test_accepts_empty_target_fields(self) -> None:
        req = AnalysisDatasetRequest(feature_fields=["temperature"], target_fields=[])
        assert req.target_fields == []


class TestAnalysisDataset:
    def test_accepts_all_fields(self) -> None:
        ds = AnalysisDataset(
            features=[{"temperature": 180.0}],
            targets=[{"diameter": 10.2}],
            metadata=[{"barcode": "B1"}],
            field_summary={"temperature": {"count": 1}},
            sample_count=1,
            truncated=False,
        )
        assert ds.sample_count == 1
        assert ds.truncated is False
        assert ds.features == [{"temperature": 180.0}]


class TestProfilingResult:
    def test_accepts_fields(self) -> None:
        pr = ProfilingResult(field="temperature", mean=180.0, std=5.0, min=170.0, max=190.0)
        assert pr.field == "temperature"


class TestCorrelationRequest:
    def test_accepts_fields(self) -> None:
        req = CorrelationRequest(field_x="temperature", field_y="diameter", method="pearson")
        assert req.field_x == "temperature"


class TestCorrelationResult:
    def test_accepts_fields(self) -> None:
        res = CorrelationResult(
            field_x="temperature",
            field_y="diameter",
            coefficient=0.95,
            p_value=0.001,
            method="pearson",
        )
        assert abs(res.coefficient - 0.95) < 1e-9


class TestImportanceRequest:
    def test_accepts_fields(self) -> None:
        req = ImportanceRequest(
            feature_fields=["temperature", "pressure"],
            target_field="diameter",
            method="random_forest",
        )
        assert req.method == "random_forest"


class TestImportanceResult:
    def test_accepts_fields(self) -> None:
        res = ImportanceResult(
            importances={"temperature": 0.7, "pressure": 0.3},
            method="random_forest",
        )
        assert res.importances["temperature"] == 0.7


class TestRegressionRequest:
    def test_accepts_fields(self) -> None:
        req = RegressionRequest(
            feature_fields=["temperature"],
            target_field="diameter",
            model_type="linear",
        )
        assert req.model_type == "linear"


class TestRegressionResult:
    def test_accepts_fields(self) -> None:
        res = RegressionResult(
            r_squared=0.85,
            rmse=0.5,
            coefficients={"temperature": 0.1},
            model_type="linear",
        )
        assert res.r_squared == 0.85


class TestRecommendationRequest:
    def test_accepts_fields(self) -> None:
        req = RecommendationRequest(
            feature_fields=["temperature"],
            target_field="diameter",
            target_value=10.0,
            constraints=[
                Constraint(field="temperature", min=150.0, max=220.0),
            ],
        )
        assert req.target_value == 10.0
        assert len(req.constraints) == 1


class TestRecommendationResult:
    def test_accepts_all_required_fields(self) -> None:
        res = RecommendationResult(
            recommended_parameters={"temperature": 185.0},
            predicted_target=10.5,
            alternatives=[{"temperature": 190.0}],
            important_features=["temperature"],
            risk_notes=["operating near upper bound"],
            model_metrics={"r_squared": 0.85},
            dataset_summary={"sample_count": 100},
            can_submit_as_proposed=True,
        )
        assert res.recommended_parameters == {"temperature": 185.0}
        assert res.can_submit_as_proposed is True

    def test_defaults_can_submit_as_proposed_to_true(self) -> None:
        res = RecommendationResult(
            recommended_parameters={"temperature": 185.0},
            predicted_target=10.5,
            alternatives=[],
            important_features=[],
            risk_notes=[],
            model_metrics={},
            dataset_summary={},
        )
        assert res.can_submit_as_proposed is True


class TestConstraint:
    def test_accepts_all_fields(self) -> None:
        c = Constraint(field="temperature", min=150.0, max=220.0)
        assert c.field == "temperature"
        assert c.min == 150.0
        assert c.max == 220.0

    def test_accepts_min_only(self) -> None:
        c = Constraint(field="temperature", min=100.0)
        assert c.max is None


# ---------------------------------------------------------------------------
# DatasetBuilder tests (real DB)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    dsn = os.environ.get(
        "PROCESS_OPT_TEST_POSTGRES_DSN",
        "postgresql://postgres:postgres@localhost:5432/process_opt",
    )
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"
    pool = await create_pool(dsn)
    try:
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as connection:
            await connection.execute("TRUNCATE process_summary, inspection_results RESTART IDENTITY")
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def insert_one_row(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO process_summary (barcode, device_id, processed_at, params)
            VALUES ($1, $2, $3, $4)
            """,
            "B1", "D1", datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
            {"temperature": 180.0, "pressure": 1.0},
        )
        await connection.execute(
            """
            INSERT INTO inspection_results (barcode, station_id, inspected_at, results)
            VALUES ($1, $2, $3, $4)
            """,
            "B1", "QA1", datetime(2026, 6, 8, 10, 5, tzinfo=UTC),
            {"diameter": 10.2, "roundness": 0.99},
        )


@pytest_asyncio.fixture
async def insert_two_rows_one_missing(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO process_summary (barcode, device_id, processed_at, params)
            VALUES ($1, $2, $3, $4), ($5, $6, $7, $8)
            """,
            "B1", "D1", datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
            {"temperature": 180.0, "pressure": 1.0},
            "B2", "D1", datetime(2026, 6, 8, 11, 0, tzinfo=UTC),
            {"temperature": 190.0},
        )
        await connection.execute(
            """
            INSERT INTO inspection_results (barcode, station_id, inspected_at, results)
            VALUES ($1, $2, $3, $4), ($5, $6, $7, $8)
            """,
            "B1", "QA1", datetime(2026, 6, 8, 10, 5, tzinfo=UTC),
            {"diameter": 10.2, "roundness": 0.99},
            "B2", "QA1", datetime(2026, 6, 8, 11, 5, tzinfo=UTC),
            {"diameter": 9.8},
        )


class TestDatasetBuilder:
    @pytest.mark.asyncio
    async def test_build_returns_dataset_with_one_sample(
        self, pool: asyncpg.Pool, insert_one_row: None,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["temperature"],
            target_fields=["diameter"],
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisDataset)
        assert result.sample_count == 1
        assert result.truncated is False
        assert result.features == [{"temperature": 180.0}]
        assert result.targets == [{"diameter": 10.2}]
        assert result.metadata == [{
            "barcode": "B1",
            "device_id": "D1",
            "station_id": "QA1",
            "processed_at": "2026-06-08T10:00:00+00:00",
            "inspected_at": "2026-06-08T10:05:00+00:00",
        }]

    @pytest.mark.asyncio
    async def test_missing_field_returns_field_not_found(
        self, pool: asyncpg.Pool, insert_one_row: None,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["nonexistent_field"],
            target_fields=["diameter"],
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisError)
        assert result.code == "FIELD_NOT_FOUND"
        assert "nonexistent_field" in result.message

    @pytest.mark.asyncio
    async def test_drop_row_missing_strategy(
        self, pool: asyncpg.Pool, insert_two_rows_one_missing: None,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["temperature", "pressure"],
            target_fields=["diameter", "roundness"],
            missing_strategy="drop_row",
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisDataset)
        assert result.sample_count == 1
        assert result.features == [{"temperature": 180.0, "pressure": 1.0}]
        assert result.targets == [{"diameter": 10.2, "roundness": 0.99}]

    @pytest.mark.asyncio
    async def test_mean_missing_strategy(
        self, pool: asyncpg.Pool, insert_two_rows_one_missing: None,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["temperature", "pressure"],
            target_fields=["diameter", "roundness"],
            missing_strategy="mean",
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisDataset)
        assert result.sample_count == 2
        assert result.features[1]["pressure"] == 1.0

    @pytest.mark.asyncio
    async def test_median_missing_strategy(
        self, pool: asyncpg.Pool, insert_two_rows_one_missing: None,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["temperature", "pressure"],
            target_fields=["diameter", "roundness"],
            missing_strategy="median",
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisDataset)
        assert result.sample_count == 2
        assert result.features[1]["pressure"] == 1.0

    @pytest.mark.asyncio
    async def test_max_samples_truncates(
        self, pool: asyncpg.Pool, insert_two_rows_one_missing: None,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["temperature"],
            target_fields=["diameter"],
            max_samples=1,
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisDataset)
        assert result.sample_count == 1
        assert result.truncated is True
        assert len(result.features) == 1

    @pytest.mark.asyncio
    async def test_insufficient_samples_returns_error(
        self, pool: asyncpg.Pool,
    ) -> None:
        from process_opt.analysis.dataset import DatasetBuilder

        builder = DatasetBuilder(pool)
        request = AnalysisDatasetRequest(
            feature_fields=["temperature"],
            target_fields=["diameter"],
        )
        result = await builder.build(request)

        assert isinstance(result, AnalysisError)
        assert result.code == "INSUFFICIENT_SAMPLES"
