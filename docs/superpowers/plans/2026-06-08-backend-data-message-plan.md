# Backend Data and Message Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1: HTTP ingestion → NATS JetStream → Consumer → PostgreSQL → query API.

**Architecture:** Use a Python `src/` monorepo with separate runtime packages: `gateway`, `consumer`, `api`, and shared `common`. Each task is test-first and independently verifiable.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, asyncpg, nats-py, PostgreSQL 15+, NATS JetStream, pytest, pytest-asyncio, httpx, ruff, mypy.

---

## File Structure

Create or modify:

```text
pyproject.toml
.env.example
docker-compose.yml
db/init-db.sql
db/migrations/001_initial.sql
src/process_opt/common/settings.py
src/process_opt/common/schemas.py
src/process_opt/common/db.py
src/process_opt/common/nats_client.py
src/process_opt/common/repositories.py
src/process_opt/gateway/app.py
src/process_opt/consumer/handler.py
src/process_opt/consumer/worker.py
src/process_opt/api/app.py
tests/conftest.py
tests/common/test_settings.py
tests/common/test_schemas.py
tests/common/test_repositories.py
tests/gateway/test_app.py
tests/consumer/test_handler.py
tests/api/test_app.py
tests/integration/test_data_pipeline.py
```

## Task 1: Project tooling and config

**Files:** `pyproject.toml`, `.env.example`, `docker-compose.yml`, `src/process_opt/common/settings.py`, `tests/common/test_settings.py`

- [ ] **Step 1: Write failing test**

Create `tests/common/test_settings.py`:

```python
from process_opt.common.settings import Settings


def test_settings_loads_defaults():
    settings = Settings()
    assert settings.gateway_api_key == "dev-api-key"
    assert settings.nats_url == "nats://localhost:4222"
    assert settings.postgres_dsn == "postgresql://postgres:postgres@localhost:5432/process_opt"
```

- [ ] **Step 2: Run failing test**

Run: `pytest tests/common/test_settings.py -v`

Expected: fails because package/settings do not exist.

- [ ] **Step 3: Implement minimal project setup**

Create `pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `asyncpg`, `nats-py`; dev dependencies: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`. Configure pytest `pythonpath = ["src"]` and mypy strict mode.

Create `src/process_opt/common/settings.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROCESS_OPT_")

    gateway_api_key: str = "dev-api-key"
    nats_url: str = "nats://localhost:4222"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/process_opt"
    nats_stream: str = "PROCESS_OPT"
    process_subject: str = "process_data"
    inspection_subject: str = "inspection_data"
```

Update `docker-compose.yml` to run `postgres:15` on `5432:5432` with database `process_opt`, and `nats:2.10` with JetStream enabled on `4222:4222`.

- [ ] **Step 4: Verify**

Run:

```bash
python -m pip install -e '.[dev]'
pytest tests/common/test_settings.py -v
ruff check .
mypy src
```

Expected: all pass.

- [ ] **Step 5: Commit**

Run: `git add . && git commit -m "chore: initialize backend project tooling"`

## Task 2: Message schemas

**Files:** `src/process_opt/common/schemas.py`, `src/process_opt/common/errors.py`, `tests/common/test_schemas.py`

- [ ] **Step 1: Write failing tests**

Create `tests/common/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError
from process_opt.common.schemas import InspectionMessage, ProcessMessage


def test_process_message_accepts_required_fields():
    msg = ProcessMessage(message_id="m1", barcode="B1", device_id="D1", processed_at="2026-06-08T10:00:00Z", params={"temperature": 180})
    assert msg.barcode == "B1"


def test_process_message_rejects_empty_params():
    with pytest.raises(ValidationError):
        ProcessMessage(message_id="m1", barcode="B1", device_id="D1", processed_at="2026-06-08T10:00:00Z", params={})


def test_inspection_message_accepts_required_fields():
    msg = InspectionMessage(message_id="m2", barcode="B1", station_id="QA1", inspected_at="2026-06-08T10:05:00Z", results={"diameter": 10.2})
    assert msg.station_id == "QA1"


def test_inspection_message_rejects_empty_results():
    with pytest.raises(ValidationError):
        InspectionMessage(message_id="m2", barcode="B1", station_id="QA1", inspected_at="2026-06-08T10:05:00Z", results={})
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/common/test_schemas.py -v`

Expected: fails because schemas do not exist.

- [ ] **Step 3: Implement schemas**

Create `src/process_opt/common/schemas.py`:

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    processed_at: datetime
    params: dict[str, Any]

    @field_validator("params")
    @classmethod
    def params_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("params must not be empty")
        return value


class InspectionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1)
    barcode: str = Field(min_length=1)
    station_id: str = Field(min_length=1)
    inspected_at: datetime
    results: dict[str, Any]

    @field_validator("results")
    @classmethod
    def results_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("results must not be empty")
        return value
```

Create `src/process_opt/common/errors.py` with `PublishError` and `MessageHandlingError` exception classes.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/common/test_schemas.py -v && ruff check . && mypy src`

Commit: `git add . && git commit -m "feat: add ingestion message schemas"`

## Task 3: Database schema and repository

**Files:** `db/init-db.sql`, `db/migrations/001_initial.sql`, `src/process_opt/common/db.py`, `src/process_opt/common/repositories.py`, `tests/common/test_repositories.py`

- [ ] **Step 1: Write failing repository test**

Create a test that starts from `PROCESS_OPT_TEST_POSTGRES_DSN`, applies `001_initial.sql`, upserts one process message twice for the same `barcode`, upserts one inspection message, then verifies `analysis_view` returns the updated process row and joined inspection row.

Core assertion code:

```python
row = await repo.get_analysis_record("B1")
assert row["barcode"] == "B1"
assert row["device_id"] == "D2"
assert row["params"]["temperature"] == 181
assert row["results"]["diameter"] == 10.1
```

- [ ] **Step 2: Run failing test**

Run:

```bash
docker compose up -d postgres
pytest tests/common/test_repositories.py -v
```

Expected: fails because DB helpers and repository do not exist.

- [ ] **Step 3: Implement SQL**

Create `db/migrations/001_initial.sql` and copy it to `db/init-db.sql`:

```sql
CREATE TABLE IF NOT EXISTS process_summary (
  barcode TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL,
  params JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inspection_results (
  barcode TEXT PRIMARY KEY,
  station_id TEXT NOT NULL,
  inspected_at TIMESTAMPTZ NOT NULL,
  results JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW analysis_view AS
SELECT p.barcode, p.device_id, p.processed_at, p.params, i.station_id, i.inspected_at, i.results
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;
```

- [ ] **Step 4: Implement repository**

Implement `apply_sql_file(pool, path)`, `DataRepository.upsert_process`, `DataRepository.upsert_inspection`, and `DataRepository.get_analysis_record`. Use `INSERT ... ON CONFLICT (barcode) DO UPDATE` and pass JSON through asyncpg JSON encoding.

- [ ] **Step 5: Verify and commit**

Run: `pytest tests/common/test_repositories.py -v && ruff check . && mypy src`

Commit: `git add . && git commit -m "feat: add database schema and repositories"`

## Task 4: Gateway ingestion API

**Files:** `src/process_opt/common/nats_client.py`, `src/process_opt/gateway/app.py`, `tests/gateway/test_app.py`

- [ ] **Step 1: Write failing gateway tests**

Test cases:

```python
async def test_process_endpoint_publishes_and_returns_202(): ...
async def test_inspection_endpoint_publishes_and_returns_202(): ...
async def test_missing_api_key_returns_401(): ...
async def test_invalid_payload_returns_422(): ...
async def test_publish_failure_returns_503(): ...
```

Use `httpx.AsyncClient` against the FastAPI app and inject a fake publisher with `publish(subject, payload)`.

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/gateway/test_app.py -v`

Expected: fails because gateway app does not exist.

- [ ] **Step 3: Implement gateway**

Create `create_app(settings, publisher)` in `gateway/app.py`. Add:

- `POST /api/v1/data/process`
- `POST /api/v1/data/inspection`
- API Key check from `X-API-Key`
- publish to configured subject
- return `202`
- convert `PublishError` to `503`

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/gateway/test_app.py -v && ruff check . && mypy src`

Commit: `git add . && git commit -m "feat: add gateway ingestion api"`

## Task 5: Consumer handler

**Files:** `src/process_opt/consumer/handler.py`, `src/process_opt/consumer/worker.py`, `tests/consumer/test_handler.py`

- [ ] **Step 1: Write failing handler tests**

Test cases:

```python
async def test_handle_process_message_upserts_and_acks(): ...
async def test_handle_inspection_message_upserts_and_acks(): ...
async def test_invalid_json_naks_or_terms_message(): ...
async def test_repository_failure_does_not_ack(): ...
```

Use fake message objects with `data`, `ack()`, `nak()`, and `term()` methods.

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/consumer/test_handler.py -v`

Expected: fails because handler does not exist.

- [ ] **Step 3: Implement handler**

Create `MessageHandler(repo)` with `handle_process(raw_msg)` and `handle_inspection(raw_msg)`. Decode JSON, validate Pydantic model, call repository, ack on success, term invalid messages, and leave DB failures unacked or nak them for retry.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/consumer/test_handler.py -v && ruff check . && mypy src`

Commit: `git add . && git commit -m "feat: add consumer message handler"`

## Task 6: Query API

**Files:** `src/process_opt/api/app.py`, `tests/api/test_app.py`

- [ ] **Step 1: Write failing API tests**

Test cases:

```python
async def test_get_analysis_record_by_barcode_returns_joined_data(): ...
async def test_get_unknown_barcode_returns_404(): ...
async def test_health_returns_ok(): ...
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/api/test_app.py -v`

Expected: fails because API app does not exist.

- [ ] **Step 3: Implement API**

Create `create_app(repository)` with:

- `GET /health`
- `GET /api/v1/analysis/records/{barcode}`
- later-compatible structure for time range queries

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/api/test_app.py -v && ruff check . && mypy src`

Commit: `git add . && git commit -m "feat: add backend query api"`

## Task 7: End-to-end integration

**Files:** `tests/integration/test_data_pipeline.py`

- [ ] **Step 1: Write failing integration test**

Test complete flow:

1. start postgres and nats with `docker compose up -d postgres nats`
2. apply migration
3. create real JetStream publisher
4. post process and inspection payloads to gateway app
5. consume messages with handler
6. query API by barcode
7. assert joined result exists

- [ ] **Step 2: Run failing test**

Run: `pytest tests/integration/test_data_pipeline.py -v`

Expected: fails until real publisher/consumer wiring is complete.

- [ ] **Step 3: Implement real NATS client and worker wiring**

Implement `JetStreamPublisher` in `common/nats_client.py` with stream creation and `publish(subject, payload)`. Implement `consumer/worker.py` to connect, pull messages, and call `MessageHandler`.

- [ ] **Step 4: Verify full suite**

Run:

```bash
docker compose up -d postgres nats
pytest -v
ruff check .
mypy src
```

Expected: all pass.

- [ ] **Step 5: Commit**

Run: `git add . && git commit -m "test: verify backend data pipeline end to end"`

## Final Verification

Run:

```bash
docker compose up -d postgres nats
pytest -v
ruff check .
mypy src
```

Expected: all tests, lint, and typecheck pass.
