# Service Entrypoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runnable development entrypoints for Gateway, Backend API, and Consumer.

**Architecture:** Keep app factories unchanged. Add thin `main` modules that wire `Settings`, NATS, DB repositories, and uvicorn/consumer loops.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, asyncpg, nats-py, pytest, ruff, mypy.

---

## Task 1: Gateway and API entrypoint modules

**Files:**
- Create: `src/process_opt/gateway/main.py`
- Create: `src/process_opt/api/main.py`
- Modify: `pyproject.toml`
- Test: `tests/test_entrypoints.py`

- [ ] Write failing tests that import `process_opt.gateway.main:create_gateway_app_from_settings` and `process_opt.api.main:create_api_app_from_settings`.
- [ ] Run `.venv/bin/python -m pytest tests/test_entrypoints.py -v`; expect import failure.
- [ ] Implement `create_gateway_app_from_settings()` returning `gateway.app.create_app(Settings(), JetStreamPublisher(Settings()))`.
- [ ] Implement `create_api_app_from_settings()` creating async startup/shutdown DB pool and `DataRepository` attached to app state.
- [ ] Add console scripts in `pyproject.toml`:
  - `process-opt-gateway = process_opt.gateway.main:main`
  - `process-opt-api = process_opt.api.main:main`
- [ ] `main()` functions call `uvicorn.run(..., host="0.0.0.0", port=8001/8000)`.
- [ ] Run `.venv/bin/python -m pytest tests/test_entrypoints.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 2: Consumer entrypoint

**Files:**
- Modify: `src/process_opt/consumer/worker.py`
- Create: `src/process_opt/consumer/main.py`
- Modify: `pyproject.toml`
- Test: `tests/test_consumer_entrypoint.py`

- [ ] Write failing tests for `process_opt.consumer.main:run_once` using fake settings/repository or monkeypatches.
- [ ] Run `.venv/bin/python -m pytest tests/test_consumer_entrypoint.py -v`; expect import failure.
- [ ] Implement `run_once(settings)` to create DB pool, repository, handler, call `consume_pending_messages`, close pool, return handled count.
- [ ] Implement `main()` loop calling `run_once(Settings())` repeatedly with small sleep.
- [ ] Add console script: `process-opt-consumer = process_opt.consumer.main:main`.
- [ ] Run `.venv/bin/python -m pytest tests/test_consumer_entrypoint.py -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Task 3: Usage smoke documentation in README

**Files:**
- Modify: `readme.md`
- Test: full verification

- [ ] Add concise development usage section:
  - `docker compose up -d postgres nats`
  - `.venv/bin/python -m pip install -e '.[dev]'` or `uv pip install --python .venv/bin/python -e '.[dev]'`
  - `process-opt-gateway`
  - `process-opt-api`
  - `process-opt-consumer`
  - example curl for process, inspection, query.
- [ ] Run `.venv/bin/python -m pytest -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy .`.

## Final Verification

Run:

```bash
docker compose up -d postgres nats
.venv/bin/python -m pytest -v
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy .
```
