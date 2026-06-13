# Frontend SPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vue 3 + Element Plus SPA providing dashboard, analysis, parameter management, and settings views.

**Architecture:** Use Vite for dev/build. Static files served by BackendAPI. SPA communicates via Axios. No authentication for first iteration — just functional UI wired to real API.

**Tech Stack:** Vue 3, Vite, Element Plus, ECharts, Vue Router, Pinia, Axios, Node.js 24.

---

## File Structure

```text
web/
  index.html
  vite.config.ts
  tsconfig.json
  package.json
  env.d.ts
  src/
    main.ts
    App.vue
    api/
      client.ts
      analysis.ts
      parameters.ts
    stores/
      analysis.ts
      parameters.ts
      session.ts
      system.ts
    views/
      DashboardView.vue
      AnalysisView.vue
      ParametersView.vue
      SettingsView.vue
      LoginView.vue
    components/
      AppLayout.vue
      AnalysisFilter.vue
      CorrelationChart.vue
      RegressionChart.vue
      RecommendationForm.vue
      ParameterStatus.vue
```

## Build Configuration

Set up:
- `package.json` with Vue 3 + Element Plus + ECharts + Vue Router + Pinia + Axios
- `vite.config.ts` with proxy `"/api"` to `http://localhost:8000` in dev, and `base: "/"` for production
- `tsconfig.json` for TypeScript
- `index.html` entry point

No auth for first iteration. Build with `npm run build`, output to `dist/`.

## Task 1: Scaffold project and API client

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/index.html`
- Create: `web/env.d.ts`
- Create: `web/src/main.ts`
- Create: `web/src/App.vue`
- Create: `web/src/api/client.ts`
- Create: `web/src/api/analysis.ts`
- Create: `web/src/api/parameters.ts`

- [ ] Run `npm --prefix web create -y` and add dependencies: vue, element-plus, echarts, vue-echarts, vue-router, pinia, axios, @element-plus/icons-vue + dev deps: vite, @vitejs/plugin-vue, typescript, vue-tsc.
- [ ] Verify `npm --prefix web install` works.
- [ ] Implement `api/client.ts` with Axios instance pointing to `/api/v1` with response interceptor for errors.
- [ ] Implement `analysis.ts` with profile, correlation, regression, recommendation API calls.
- [ ] Implement `parameters.ts` with create, submit, approve, reject, activate, latest, confirmation calls.
- [ ] Export and verify with `npx --prefix web vue-tsc --noEmit`.

## Task 2: Layout and routing

**Files:**
- Create: `web/src/router/index.ts`
- Create: `web/src/stores/session.ts`
- Create: `web/src/components/AppLayout.vue`

- [ ] Set up Vue Router with routes: `/login`, `/dashboard`, `/analysis`, `/parameters`, `/settings`.
- [ ] Create `AppLayout.vue` with sidebar (ElMenu) + header area + content area.
- [ ] Create session store for current user and role.
- [ ] Wire AppLayout in App.vue with router-view.
- [ ] Verify with `npx --prefix web vue-tsc --noEmit`.

## Task 3: Dashboard view

**Files:**
- Create: `web/src/views/DashboardView.vue`
- Create: `web/src/stores/system.ts`

- [ ] Create `system.ts` store with service status, daily counts, resources.
- [ ] Dashboard shows cards for service status, today data count, pending approvals using ElCard + ElTag.
- [ ] Verify with `npx --prefix web vue-tsc --noEmit`.

## Task 4: Analysis view

**Files:**
- Create: `web/src/views/AnalysisView.vue`
- Create: `web/src/stores/analysis.ts`
- Create: `web/src/components/AnalysisFilter.vue`
- Create: `web/src/components/CorrelationChart.vue`
- Create: `web/src/components/RegressionChart.vue`
- Create: `web/src/components/RecommendationForm.vue`

- [ ] AnalysisView with tabs: Profile / Correlation / Regression / Recommendation.
- [ ] AnalysisFilter with time range, feature fields, target fields.
- [ ] CorrelationChart uses ECharts heatmap.
- [ ] RegressionChart uses ECharts scatter plot.
- [ ] RecommendationForm with tunable params, bounds, submit button.
- [ ] Verify with `npx --prefix web vue-tsc --noEmit`.

## Task 5: Parameters and settings view

**Files:**
- Create: `web/src/views/ParametersView.vue`
- Create: `web/src/views/SettingsView.vue`
- Create: `web/src/components/ParameterStatus.vue`

- [ ] ParametersView: table of parameter sets with status badges, approve/reject/activate buttons, device confirmations.
- [ ] SettingsView: service control (start/stop/restart), config view (read-only first), logs (placeholder).
- [ ] Verify with `npx --prefix web vue-tsc --noEmit`.

## Task 6: Build and BackendAPI integration

**Files:**
- Modify: `web/vite.config.ts` (production base)
- Modify: `src/process_opt/api/app.py` (serve static files)
- Test: manual build verification

- [ ] Build with `npm --prefix web run build`.
- [ ] Mount static dir in BackendAPI using `FastAPI.mount("/", StaticFiles(directory="web/dist", html=True))`.
- [ ] Ensure SPA routing works (catch-all fallback to index.html).
- [ ] Run `process-opt-api` and verify frontend loads at `http://localhost:8000`.

## Task 7: Final verification

```bash
docker compose up -d postgres nats
# Start backend services
npm --prefix web run build
# Verify BackendAPI serves frontend
# Verify frontend can call all API endpoints
.venv/bin/python -m pytest -v
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy .
```
