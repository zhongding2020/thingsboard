# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

工艺参数在线分析与调优系统 (Process Parameter Online Analysis & Optimization System) — a lightweight, self-contained manufacturing process optimization platform for small-to-medium factories. Built entirely in Python with a Vue 3 frontend, deployed as a single Windows installer. No third-party IoT platforms (no ThingsBoard/Kafka/Java).

## Essential Commands

### Start dependencies (dev)
```bash
docker compose up -d postgres nats     # PostgreSQL 15 + NATS JetStream
```

### Install
```bash
uv pip install --python .venv/bin/python -e '.[dev]'
```

### Run services (three separate terminals)
```bash
process-opt-gateway      # Data ingestion gateway, port 8001
process-opt-consumer     # NATS→PostgreSQL message consumer
process-opt-api          # Backend API + serves frontend, port 8000
```

### Frontend
```bash
cd web && npm run dev        # Vite dev server
cd web && npm run build      # Production build → web/dist/
cd web && npm run typecheck  # vue-tsc --noEmit
```

### Tests, lint, typecheck
```bash
pytest                                  # All tests (pythonpath = src from pyproject.toml)
pytest tests/test_entrypoints.py -v     # Single test file
ruff check .                            # Lint
mypy                                    # Strict type checking (config in pyproject.toml)
```

### Test data upload
```bash
curl -X POST http://localhost:8001/api/v1/data/process \
  -H 'Content-Type: application/json' -H 'X-API-Key: dev-api-key' \
  -d '{"message_id":"p1","barcode":"B1","device_id":"D1","processed_at":"2026-06-08T10:00:00Z","params":{"temperature":180}}'
```

### Generate mock data
```bash
process-opt-mock --help
```

## Architecture

### Service topology

```
[Devices] → HTTP POST → [Gateway :8001] → NATS JetStream → [Consumer] → PostgreSQL
                                                              ↓
[Browser] ← SPA ← [Backend API :8000] ← PostgreSQL
                       ↓
                 [LangGraph Agent] (Supervisor → chat/analyzer/recommender Workers)
```

### Four runnable entrypoints

| Entrypoint | Module | Role |
|---|---|---|
| `process-opt-gateway` | `process_opt.gateway.main` | Accepts device HTTP POSTs, validates JSON, publishes to NATS, returns 202 |
| `process-opt-consumer` | `process_opt.consumer.main` | Pulls from NATS JetStream, UPSERTs into PostgreSQL, Acks on success |
| `process-opt-api` | `process_opt.api.main` | Unified FastAPI backend — analysis APIs, parameter management, agent chat, SPA serving |
| `process-opt-mock` | `process_opt.mock.cli` | Generates synthetic process/inspection data for testing |

### Source layout (`src/process_opt/`)

| Package | Purpose |
|---|---|
| `gateway/` | HTTP ingestion gateway, validates & publishes to NATS |
| `consumer/` | NATS JetStream consumer, writes to PostgreSQL |
| `api/` | FastAPI app factory (`app.py`), agent SSE routes (`agent_routes.py`), entrypoint (`main.py`) |
| `agent/` | LangGraph agent: `graph.py` (builds StateGraph), `nodes/supervisor.py`, `nodes/worker.py`, `state.py`, `tools/analysis_tools.py` |
| `analysis/` | Statistical analysis engine: correlation, regression (linear/PLS), feature importance, SPC, DOE, Pareto, optimization, profiling, recommendation, report generation |
| `parameters/` | Parameter set lifecycle: state machine (draft→proposed→approved→active→archived), repository, approval workflow |
| `knowledge/` | Process templates as JSON files (`templates/*.json`), loader, rule engine for constraint validation |
| `common/` | Settings (pydantic-settings, `PROCESS_OPT_` env prefix), DB pool, NATS client, data schemas, error types |
| `experiment/` | DOE experiment plan persistence and result recording |
| `mock/` | Synthetic data generator with per-process-type templates |

### Agent architecture (LangGraph)

**Supervisor-Worker pattern** with structured output routing:

1. `Supervisor` node receives user message, classifies intent via `SupervisorDecision` (CHAT/ANALYZER/RECOMMENDER/FINISH), routes accordingly
2. Three worker nodes (`chat`, `analyzer`, `recommender`) — each receives role-specific system prompt + process knowledge template (loaded from `knowledge/templates/{process_type}.json`)
3. Workers call tools (20+ LangChain `@tool` functions) which invoke analysis APIs and return pre-formatted Markdown
4. Tool results route back to supervisor, which decides next step or FINISH

Key files: [graph.py](src/process_opt/agent/graph.py), [supervisor.py](src/process_opt/agent/nodes/supervisor.py), [worker.py](src/process_opt/agent/nodes/worker.py), [analysis_tools.py](src/process_opt/agent/tools/analysis_tools.py)

### API design pattern

The FastAPI app is built via a **factory function** `create_app()` in [app.py](src/process_opt/api/app.py) that accepts dependencies as Protocol-typed parameters. Routes are conditionally registered only when their dependency is provided. This enables:
- Testing with mock dependencies
- Graceful degradation when optional services are unavailable
- Clean separation of route groups (analysis, parameters, lines/devices, experiments, agent)

### SSE streaming

Agent chat uses Server-Sent Events (SSE) at `GET /api/v1/agent/chat/{session_id}/events`. The `_map_event()` function in [agent_routes.py](src/process_opt/api/agent_routes.py) converts LangGraph streaming events (`on_chat_model_stream`, `on_tool_start`, `on_tool_end`, `on_chain_start/end`) into typed SSE messages consumed by the frontend.

### Session management

`SessionManager` in [graph.py](src/process_opt/agent/graph.py) holds in-memory `AgentSession` objects with TTL-based expiry (default 30 min). Each session wraps a compiled LangGraph graph with its own `thread_id` for conversation state isolation.

### Knowledge templates

Process knowledge is declarative JSON files in [src/process_opt/knowledge/templates/](src/process_opt/knowledge/templates/). Each defines: parameters (range/target/importance), quality metrics (USL/LSL), constraints (hard/soft/dependency), and analysis hints. `KnowledgeLoader.build_system_prompt()` converts them into LLM system prompts.

### Database

PostgreSQL 15 with JSONB columns for flexible process/inspection data storage. Key tables: `process_summary`, `inspection_results`, `parameter_sets`, `parameter_items`, `parameter_confirmations`, `production_lines`, `device_registry`. An `analysis_view` LEFT JOINs process + inspection on barcode. Schema is in [db/init-db.sql](db/init-db.sql).

### Configuration

All settings via environment variables with `PROCESS_OPT_` prefix (see [settings.py](src/process_opt/common/settings.py)). Key vars: `PROCESS_OPT_POSTGRES_DSN`, `PROCESS_OPT_NATS_URL`, `PROCESS_OPT_GATEWAY_API_KEY`, `PROCESS_OPT_AGENT_API_KEY`, `PROCESS_OPT_AGENT_MODEL`.

## Knowledge Graph (graphify)

When exploring codebase structure, relationships, or architecture, **always use graphify first** — it produces a persistent knowledge graph from AST extraction (zero LLM cost) with community detection, god nodes, and query capabilities.

```bash
graphify query "<question>"                         # BFS traversal — broad context
graphify query "<question>" --dfs                    # DFS — trace specific path
graphify path "<node>" "<node>"                     # shortest path between two concepts
graphify explain "<node>"                           # plain-language explanation of a node
```

**If graph.json does not exist** (first run or after major changes):
```bash
graphify export html    # rebuild graph (automatic from detect→extract→build)
```

The graph output lives in `graphify-out/`:
- `graph.html` — interactive browser visualization
- `graph.json` — raw graph data
- `GRAPH_REPORT.md` — audit report with communities, god nodes, surprising connections

**Rule**: Before asking "how does X relate to Y" or "what modules call Z", run `graphify path "X" "Y"` or `graphify query "what does Z depend on"`. The graph has ~2100 nodes / ~4000 edges / ~150 communities — most cross-module answers are one query away.

## Development notes

- **Python 3.11+** required. Dependencies managed with `uv` (see `uv.lock`).
- **Tests use `pytest`** with `pythonpath = ["src"]` in pyproject.toml — imports work as `from process_opt.xxx`.
- **Frontend is Vue 3 + Element Plus + Pinia + Vite**. Build output goes to `web/dist/`, which the backend serves as static files via a catch-all SPA route.
- **The repo is named "thingsboard"** on disk but the Python package is `process-opt` / `process_opt`. The web project is named "thingsboard-web" in `package.json` — this is a legacy naming artifact.
- **Tool retries**: Agent tools use a `@with_retry()` decorator from [tools/retry.py](src/process_opt/agent/tools/retry.py) that catches exceptions and returns error strings instead of crashing the graph.
- **Mock data**: `process-opt-mock` CLI generates realistic data for 8 process types (点胶固化, 注塑成型, 压铸, CNC加工, 回流焊, 热处理, 焊接, 粉末涂装).
- **Docker Compose** provides the full stack (postgres + nats + gateway + consumer + backend-api) for development.
