# Parameter State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement parameter set lifecycle, approval, activation, latest pull, confirmation, and audit events.

**Architecture:** Add a focused `process_opt.parameters` package with schemas, errors, state machine, repository, and service. Extend the existing DB migration and API app without introducing authentication/RBAC yet.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, asyncpg, PostgreSQL, pytest, ruff, mypy.

---

## File Structure

Create or modify:

```text
db/migrations/001_initial.sql
db/init-db.sql
src/process_opt/parameters/__init__.py
src/process_opt/parameters/errors.py
src/process_opt/parameters/schemas.py
src/process_opt/parameters/state_machine.py
src/process_opt/parameters/repository.py
src/process_opt/parameters/service.py
src/process_opt/api/app.py
tests/parameters/test_state_machine.py
tests/parameters/test_repository.py
tests/parameters/test_service.py
tests/api/test_parameters_api.py
```

## Task 1: State machine and schemas

**Files:**
- Create: `src/process_opt/parameters/errors.py`
- Create: `src/process_opt/parameters/schemas.py`
- Create: `src/process_opt/parameters/state_machine.py`
- Test: `tests/parameters/test_state_machine.py`

- [ ] Write failing tests for allowed transitions: `draft->proposed`, `proposed->approved`, `proposed->rejected`, `approved->active`, `active->archived`, `approved->archived`.
- [ ] Write failing tests for forbidden transitions: `proposed->active`, `rejected->active`, `archived->active`, `active->draft`, `active->proposed`.
- [ ] Run `.venv/bin/python -m pytest tests/parameters/test_state_machine.py -v`; expect import failure.
- [ ] Implement `ParameterStatus` enum, `ParameterSetCreate`, `ParameterItemCreate`, `ParameterSet`, `ParameterItem`, `ParameterConfirmationCreate` schemas.
- [ ] Implement `validate_transition(from_status, to_status)` that raises `InvalidTransitionError` with code `INVALID_TRANSITION`.
- [ ] Run `.venv/bin/python -m pytest tests/parameters/test_state_machine.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 2: Database tables and repository

**Files:**
- Modify: `db/migrations/001_initial.sql`
- Modify: `db/init-db.sql`
- Create: `src/process_opt/parameters/repository.py`
- Test: `tests/parameters/test_repository.py`

- [ ] Write failing repository tests that apply migration and create a draft parameter set with items.
- [ ] Test same `device_type` version increments from 1 to 2.
- [ ] Test event insertion for create/submit/approve/activate/archive.
- [ ] Test confirmation insertion for `fetched`, `applied`, `failed`.
- [ ] Run `.venv/bin/python -m pytest tests/parameters/test_repository.py -v`; expect failure.
- [ ] Extend migration with `parameter_sets`, `parameter_items`, `parameter_set_events`, `parameter_confirmations`.
- [ ] Add unique `(device_type, version)` and partial unique index for one active set per `device_type`.
- [ ] Implement repository methods: `create_set`, `get_set`, `list_items`, `add_event`, `update_status`, `get_latest_active`, `insert_confirmation`, `next_version`.
- [ ] Run `.venv/bin/python -m pytest tests/parameters/test_repository.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 3: Service lifecycle behavior

**Files:**
- Create: `src/process_opt/parameters/service.py`
- Test: `tests/parameters/test_service.py`

- [ ] Write failing tests for create draft, submit, approve, reject, activate, latest, confirmation.
- [ ] Test activating a new approved set archives old active set in the same transaction.
- [ ] Test immutable states reject item edits by service design: service only creates items at set creation.
- [ ] Run `.venv/bin/python -m pytest tests/parameters/test_service.py -v`; expect failure.
- [ ] Implement `ParameterService` wrapping repository and state machine.
- [ ] Activation must archive old active and activate target in one repository transaction.
- [ ] Latest response must include `checksum`, computed from stable JSON of version/items.
- [ ] Run `.venv/bin/python -m pytest tests/parameters/test_service.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 4: Parameter API routes

**Files:**
- Modify: `src/process_opt/api/app.py`
- Test: `tests/api/test_parameters_api.py`

- [ ] Write failing API tests for:
  - `POST /api/v1/parameters/sets`
  - `POST /api/v1/parameters/sets/{id}/submit`
  - `POST /api/v1/parameters/sets/{id}/approve`
  - `POST /api/v1/parameters/sets/{id}/reject`
  - `POST /api/v1/parameters/sets/{id}/activate`
  - `GET /api/v1/parameters/latest?device_type=...&device_id=...`
  - `POST /api/v1/parameters/confirmations`
- [ ] Run `.venv/bin/python -m pytest tests/api/test_parameters_api.py -v`; expect failure.
- [ ] Extend `create_app` to optionally accept a `parameter_service`.
- [ ] Add routes mapping service errors to structured JSON errors with codes from spec.
- [ ] Run `.venv/bin/python -m pytest tests/api/test_parameters_api.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 5: Integration and final verification

**Files:**
- Test: `tests/integration/test_parameter_lifecycle.py`

- [ ] Write integration test using PostgreSQL that creates, submits, approves, activates, pulls latest, and records confirmation through API.
- [ ] Run `.venv/bin/python -m pytest tests/integration/test_parameter_lifecycle.py -v`; expect failure.
- [ ] Add any missing wiring in `api/main.py` so runtime API uses `ParameterService`.
- [ ] Run final verification:

```bash
docker compose up -d postgres nats
.venv/bin/python -m pytest -v
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy .
```

Expected: all pass.
