# Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Docker production deployment with 5 containers (postgres, nats, gateway, consumer, backend-api), single Dockerfile, and docker-compose orchestration.

**Architecture:** Single `python:3.11-slim` Dockerfile installs all Python dependencies and copies built frontend. Three shell scripts serve as container entrypoints. docker-compose manages networking, volumes, health checks, and startup order.

**Tech Stack:** Docker, docker-compose, Python 3.11, Bash.

---

## File Structure

Create or modify:

```text
Dockerfile
.dockerignore
scripts/run-gateway.sh
scripts/run-consumer.sh
scripts/run-api.sh
docker-compose.yml
```

## Task 1: Dockerfile and entrypoint scripts

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `scripts/run-gateway.sh`
- Create: `scripts/run-consumer.sh`
- Create: `scripts/run-api.sh`

- [ ] Create `.dockerignore` excluding: `.venv/`, `__pycache__/`, `.git/`, `node_modules/`, `tests/`, `web/node_modules/`.
- [ ] Create `Dockerfile`:
  - FROM `python:3.11-slim`.
  - Install system deps: `libpq-dev gcc`.
  - WORKDIR `/app`.
  - Copy `pyproject.toml` and `src/`, run `pip install .`.
  - Copy `scripts/` and `web/dist/`.
  - Run `npm --prefix web build` not needed — dist is prebuilt.
- [ ] Create `scripts/run-gateway.sh`: loops checking nats TCP port `nats:4222` (using `nc -z` or `bash /dev/tcp`), then runs `process-opt-gateway`.
- [ ] Create `scripts/run-consumer.sh`: loops checking nats port and postgres port `postgres:5432`, then runs `process-opt-consumer`.
- [ ] Create `scripts/run-api.sh`: loops checking postgres port, then runs `process-opt-api`.
- [ ] All scripts use `set -e` and `exec` to hand off PID 1.
- [ ] Test image builds: `docker build -t process-opt:latest .` passes.

## Task 2: Production docker-compose.yml

**Files:**
- Replace: `docker-compose.yml`

- [ ] Write production docker-compose.yml with 5 services:
  - `postgres`: as before, with `pgdata` volume and healthcheck.
  - `nats`: image `nats:2.10`, command `-js -sd /data -m 8222`, healthcheck via curl to `localhost:8222/healthz`.
  - `gateway`: build: `.`, command `scripts/run-gateway.sh`, ports `8001:8001`, depends_on nats (healthy), environment variables for config.
  - `consumer`: build: `.`, command `scripts/run-consumer.sh`, depends_on postgres (healthy) and nats (healthy).
  - `backend-api`: build: `.`, command `scripts/run-api.sh`, ports `8000:8000`, depends_on postgres (healthy).
- [ ] Add `nats-data` volume.
- [ ] Add `backend` network.

## Task 3: Build frontend and final verification

- [ ] Run `npm --prefix web run build`.
- [ ] Run `docker build -t process-opt:latest .` — verify success.
- [ ] Run `docker compose up -d` — all services start without errors.
- [ ] Verify health: curl `localhost:8000/health`, curl `localhost:8001/api/v1/data/process` with wrong key returns 401.
- [ ] Verify frontend loads at `localhost:8000`.
- [ ] Run `.venv/bin/python -m pytest -v && ruff check . && mypy .`.
