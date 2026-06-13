# Analysis and Recommendation Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build dataset construction, profiling, correlation, feature importance, regression, and parameter recommendation on top of `analysis_view`.

**Architecture:** Add `process_opt.analysis` package with submodules: `dataset`, `errors`, `profiling`, `correlation`, `importance`, `regression`, `recommendation`. All algorithms run in-process. API routes go into `api/app.py`. Models are scikit-learn/statsmodels only.

**Tech Stack:** Python 3.11, FastAPI, scikit-learn, statsmodels, numpy, pandas, pytest, ruff, mypy.

---

## File Structure

Create or modify:

```text
src/process_opt/analysis/__init__.py
src/process_opt/analysis/errors.py
src/process_opt/analysis/schemas.py
src/process_opt/analysis/dataset.py
src/process_opt/analysis/profiling.py
src/process_opt/analysis/correlation.py
src/process_opt/analysis/importance.py
src/process_opt/analysis/regression.py
src/process_opt/analysis/recommendation.py
src/process_opt/api/app.py
pyproject.toml
tests/analysis/test_dataset.py
tests/analysis/test_profiling.py
tests/analysis/test_correlation.py
tests/analysis/test_importance.py
tests/analysis/test_regression.py
tests/analysis/test_recommendation.py
tests/api/test_analysis_api.py
```

## Task 1: Errors, schemas, and dataset builder

**Files:**
- Create: `src/process_opt/analysis/errors.py`
- Create: `src/process_opt/analysis/schemas.py`
- Create: `src/process_opt/analysis/dataset.py`
- Test: `tests/analysis/test_dataset.py`

- [ ] Write failing tests for error classes and dataset builder.
- [ ] Test error codes: `EMPTY_DATASET`, `INSUFFICIENT_SAMPLES`, `FIELD_NOT_FOUND`, `NON_NUMERIC_FIELD`, `TOO_MANY_SAMPLES`, `SEARCH_SPACE_TOO_LARGE`, `MODEL_FIT_FAILED`, `INVALID_CONSTRAINT`.
- [ ] Test all dataset validation rules (missing strategy drop_row/mean/median, field not found, non-numeric field, insufficient samples, max_samples truncation with truncated flag).
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_dataset.py -v`; expect import failure.
- [ ] Implement `AnalysisError` with `code`/`message`/`details`/`suggestion`.
- [ ] Implement schemas: `AnalysisDatasetRequest`, `AnalysisDataset`, `ProfilingResult`, `CorrelationRequest`, `CorrelationResult`, `ImportanceRequest`, `ImportanceResult`, `RegressionRequest`, `RegressionResult`, `RecommendationRequest`, `RecommendationResult`, `Constraint`.
- [ ] Implement `DatasetBuilder` with real DB query (parameterized), JSONB key extraction into columns, missing value handling, and validation.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_dataset.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 2: Profiling module

**Files:**
- Create: `src/process_opt/analysis/profiling.py`
- Test: `tests/analysis/test_profiling.py`

- [ ] Write failing tests for profiling with known DataFrame (numpy arrays, no DB needed).
- [ ] Test fields list, types, missing rate, range, mean, std, IQR outlier counts.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_profiling.py -v`; expect import failure.
- [ ] Implement `profile_dataset(dataset: AnalysisDataset) -> ProfilingResult`.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_profiling.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 3: Correlation module

**Files:**
- Create: `src/process_opt/analysis/correlation.py`
- Test: `tests/analysis/test_correlation.py`
- Modify: `pyproject.toml` (add scipy)

- [ ] Write failing tests for Pearson and Spearman with known correlated arrays.
- [ ] Test output shape and ordering by absolute coefficient.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_correlation.py -v`; expect import failure.
- [ ] Add `scipy` dependency to pyproject.toml.
- [ ] Implement `compute_correlation(features: pd.DataFrame, targets: pd.DataFrame, method: str) -> CorrelationResult`.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_correlation.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 4: Feature importance module

**Files:**
- Create: `src/process_opt/analysis/importance.py`
- Test: `tests/analysis/test_importance.py`
- Modify: `pyproject.toml` (add scikit-learn)

- [ ] Write failing tests for linear model coefficient importance and RandomForest importance.
- [ ] Test with synthetic data producing known feature order.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_importance.py -v`; expect import failure.
- [ ] Add `scikit-learn` dependency to pyproject.toml.
- [ ] Implement `compute_importance(features, target, method) -> ImportanceResult`.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_importance.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 5: Regression module

**Files:**
- Create: `src/process_opt/analysis/regression.py`
- Test: `tests/analysis/test_regression.py`
- Modify: `pyproject.toml` (add statsmodels)

- [ ] Write failing tests for linear regression and PLS regression.
- [ ] Test with known linear data: predict close to actual, R² > 0.9.
- [ ] Test MODEL_FIT_FAILED on degenerate input.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_regression.py -v`; expect import failure.
- [ ] Add `statsmodels` dependency to pyproject.toml.
- [ ] Implement `fit_regression(features, target, model_type) -> RegressionResult`.
- [ ] Return R², RMSE, MAE, residual summary, actual vs predicted samples, model type.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_regression.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 6: Recommendation engine

**Files:**
- Create: `src/process_opt/analysis/recommendation.py`
- Test: `tests/analysis/test_recommendation.py`

- [ ] Write failing tests for recommendation with simulated regression model.
- [ ] Test: recommendation respects bounds, respects fixed params, respects constraints, SEARCH_SPACE_TOO_LARGE error when candidates exceed limit.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_recommendation.py -v`; expect import failure.
- [ ] Implement `compute_recommendation(features_df, target_df, request: RecommendationRequest) -> RecommendationResult`.
- [ ] Generate candidates from grid, fit regression, filter constraints, sort by objective, return best + alternatives.
- [ ] Run `.venv/bin/python -m pytest tests/analysis/test_recommendation.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 7: Analysis API routes

**Files:**
- Modify: `src/process_opt/api/app.py`
- Test: `tests/api/test_analysis_api.py`

- [ ] Write failing API tests for:
  - `POST /api/v1/analysis/profile`
  - `POST /api/v1/analysis/correlation`
  - `POST /api/v1/analysis/importance`
  - `POST /api/v1/analysis/regression`
  - `POST /api/v1/analysis/recommendation`
  - `POST /api/v1/analysis/recommendation/submit`
  - Error cases with structured error responses.
- [ ] Use fake AnalysisService Protocol.
- [ ] Run `.venv/bin/python -m pytest tests/api/test_analysis_api.py -v`; expect failure.
- [ ] Add AnalysisService Protocol to api/app.py.
- [ ] Add all 6 routes mapping errors to structured JSON (code/message/details/suggestion).
- [ ] Run `.venv/bin/python -m pytest tests/api/test_analysis_api.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 8: Integration and final verification

**Files:**
- Modify: `src/process_opt/api/main.py` (wire analysis service)
- Test: `tests/integration/test_analysis_pipeline.py`

- [ ] Write integration test that:
  - uploads process + inspection data via `process-opt-gateway`
  - consumes via `process-opt-consumer`
  - calls profile/correlation/regression/recommendation/submit on the real API
- [ ] Wire analysis service in `create_api_app_from_settings()`.
- [ ] Run final verification:

```bash
docker compose up -d postgres nats
.venv/bin/python -m pytest -v
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy .
```

Expected: all pass.
