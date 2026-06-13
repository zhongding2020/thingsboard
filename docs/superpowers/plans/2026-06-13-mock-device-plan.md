# Mock Device Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build mock device CLI tool that generates and sends process parameter + inspection data to Gateway.

**Architecture:** Add `process_opt.mock` package with templates, generator, HTTP sender, and CLI. Tool sends data to real Gateway HTTP endpoint.

**Tech Stack:** Python 3.11, httpx, click, pytest.

---

## File Structure

Create:

```text
src/process_opt/mock/__init__.py
src/process_opt/mock/templates.py
src/process_opt/mock/generator.py
src/process_opt/mock/sender.py
src/process_opt/mock/cli.py
tests/mock/test_generator.py
tests/mock/test_sender.py
pyproject.toml
```

## Task 1: Templates

**Files:**
- Create: `src/process_opt/mock/templates.py`
- Test: `tests/mock/test_templates.py`

- [ ] Write test verifying both device types (reflow-oven, injection-molder) are defined with required fields: params keys, results keys, range/mu/sigma/precision.
- [ ] Run `.venv/bin/python -m pytest tests/mock/test_templates.py -v`; expect failure.
- [ ] Implement `DEVICE_TEMPLATES` dict: each template has `params` (name→{min,max,mu,sigma,precision}) and `results` (name→{}) with correlation config.
- [ ] Run verify: `.venv/bin/python -m pytest tests/mock/test_templates.py -v && ruff check . && mypy .`.

## Task 2: Generator

**Files:**
- Create: `src/process_opt/mock/generator.py`
- Test: `tests/mock/test_generator.py`

- [ ] Write test `test_generate_params_returns_valid_values_in_range`.
- [ ] Write test `test_generate_results_has_weak_correlation_with_params` (temperature high → quality lower, on average).
- [ ] Write test `test_generate_pair_returns_both_process_and_inspection`.
- [ ] Write test `test_about_5_percent_anomalies` (run 1000 samples, expect 30-70 anomalies).
- [ ] Run `.venv/bin/python -m pytest tests/mock/test_generator.py -v`; expect failure.
- [ ] Implement `generate_params(device_type)`, `generate_results(device_type, params)`, `generate_pair(device_type, barcode)`. Use random.gauss + clamp. Results use weak linear correlation with noise. Anomalies: 5% chance of extreme low value.
- [ ] Run `.venv/bin/python -m pytest tests/mock/test_generator.py -v && ruff check . && mypy .`.

## Task 3: HTTP Sender

**Files:**
- Create: `src/process_opt/mock/sender.py`
- Test: `tests/mock/test_sender.py`
- Modify: `pyproject.toml` add httpx

- [ ] Write test using httpx mock (respx or httpx.MockTransport) that sender posts process and inspection to correct URLs with correct headers.
- [ ] Run `.venv/bin/python -m pytest tests/mock/test_sender.py -v`; expect failure.
- [ ] Add httpx to pyproject.toml, `uv pip install --python .venv/bin/python httpx`.
- [ ] Implement `send_pair(gateway_url, api_key, process_payload, inspection_payload)` returning bool for success.
- [ ] Implement `send_batch(gateway_url, api_key, pairs, callback)` returning (sent, failed) counts.
- [ ] Run `.venv/bin/python -m pytest tests/mock/test_sender.py -v && ruff check . && mypy .`.

## Task 4: CLI

**Files:**
- Create: `src/process_opt/mock/cli.py`
- Modify: `pyproject.toml` (console scripts)
- Test: integration (manual run)

- [ ] Not adding automated CLI tests; verify by running.
- [ ] Implement `seed(count, device_type, gateway_url, api_key, start_date)`.
- [ ] Implement `stream(interval, device_type, gateway_url, api_key)`.
- [ ] Add console script: `process-opt-mock = process_opt.mock.cli:main` using click.
- [ ] Run `process-opt-mock seed --count 5` against running Gateway, verify 202 responses.

## Task 5: Final verification

- [ ] `.venv/bin/python -m pytest tests/mock/ -v && ruff check . && mypy .`.
- [ ] `docker compose up -d postgres nats gateway`; sleep 3.
- [ ] `process-opt-mock seed --count 10`; verify sent successfully.
- [ ] Query API: `curl http://localhost:8000/api/v1/analysis/records/{last_barcode}` returns data.
