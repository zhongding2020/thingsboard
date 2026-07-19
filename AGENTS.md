# Repository instructions

## Sources of truth

- The root is the Python 3.11+ `process-opt` distribution (`src/process_opt`); `web/` is a separate Vue 3/Vite package with its own lockfile. There is no workspace-level task runner.
- Prefer `pyproject.toml`, `web/package.json`, runtime wiring, and `db/migrations/` over `readme.md` or `CLAUDE.md`; both prose files contain stale architecture and packaging details.
- The current assistant is a DeepAgent assembled in `src/process_opt/agent/deep_agent.py` from packaged Markdown skills. Do not reintroduce the obsolete Supervisor/Worker graph described in `CLAUDE.md`.
- Keep coding-agent guidance here. Runtime industrial-assistant prompts belong under `src/process_opt/agent/skills/`.

## Setup and run

- Install the Python package with dev dependencies: `uv pip install --python .venv/bin/python -e '.[dev]'` (on Windows, use the equivalent `.venv\Scripts\python.exe -m pip install -e ".[dev]"`).
- Start local dependencies before services or integration tests: `docker compose up -d postgres nats`.
- Run the three services separately: `process-opt-gateway` (8001), `process-opt-consumer`, and `process-opt-api` (8000). `process-opt-mock --help` documents synthetic-data commands.
- Frontend commands run from `web/`: `npm install`, `npm run dev`, `npm run typecheck`, `npm run build`. Vite proxies `/api` to `http://localhost:8000`; there is no frontend test or lint script.
- Build `web/dist` before `docker compose build`; the root Dockerfile copies that ignored/generated directory and does not build it.
- Settings load root `.env` and require the `PROCESS_OPT_` prefix. `.env.example` currently names the agent key incorrectly; use `PROCESS_OPT_AGENT_API_KEY`. The Python entrypoints hard-code ports 8000/8001, so the compose `*_PORT` variables do not change listeners.
- Treat any committed agent credential in `docker-compose.yml` as compromised; never copy it into code, tests, docs, or new configuration. Inject secrets through environment configuration.

## Verification

- Python: `ruff check .`, `mypy src`, then `pytest`.
- Focus a test with `pytest path/to/test.py::test_name -v`; for example, `pytest tests/test_entrypoints.py::test_create_api_app_from_settings_returns_fastapi_app -v`.
- Database-backed tests default to the local `process_opt` database and may migrate, `TRUNCATE`, or `DELETE` tables. Use a disposable database via `PROCESS_OPT_TEST_POSTGRES_DSN`. The pipeline integration test also needs NATS and accepts `PROCESS_OPT_TEST_NATS_URL`.
- Run the pipeline test with `pytest tests/integration/test_data_pipeline.py::test_http_to_nats_to_database_to_query_api_pipeline -v` after starting PostgreSQL and NATS.
- For frontend changes, run `npm run typecheck` and `npm run build` from `web/`.
- Agent-related tests still contain stale expectations for removed `_map_event` streaming and the pre-interaction DeepAgent prompt. Update tests to the current implementation; do not restore obsolete APIs just to satisfy them.

## Architecture and data-flow traps

- Entrypoints are declared in `pyproject.toml`: gateway HTTP ingestion → NATS JetStream → consumer → PostgreSQL; the backend API queries PostgreSQL and conditionally serves `web/dist`.
- The live chat contract is `POST /api/chat` using the UI Message Stream protocol. `agent_routes.py` sends only the latest user message because the LangGraph checkpointer retains thread history; old `/api/v1/agent/*` documentation is obsolete.
- API startup lexically reapplies every `db/migrations/*.sql`; make migrations replay-safe. `db/init-db.sql` is not the complete current schema and must not replace the migration chain.
- Generated artifacts include `web/dist`, virtual environments, bytecode, egg-info, and Windows build output; edit their sources instead.
- `windows-build/` is a separate release pipeline. `windows-build/build-all.bat` orders frontend install/build, Python packaging, then Inno Setup compilation; do not change that order.
