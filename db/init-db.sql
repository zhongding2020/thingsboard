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

CREATE TABLE IF NOT EXISTS parameter_sets (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  device_type TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'proposed', 'approved', 'rejected', 'active', 'archived')),
  source TEXT NOT NULL,
  created_by TEXT NOT NULL,
  approved_by TEXT,
  activated_by TEXT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  approved_at TIMESTAMPTZ,
  activated_at TIMESTAMPTZ,
  archived_at TIMESTAMPTZ,
  UNIQUE (device_type, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_parameter_sets_one_active_per_device_type
ON parameter_sets (device_type)
WHERE status = 'active';

CREATE TABLE IF NOT EXISTS parameter_items (
  id BIGSERIAL PRIMARY KEY,
  set_id BIGINT NOT NULL REFERENCES parameter_sets(id) ON DELETE CASCADE,
  param_key TEXT NOT NULL,
  param_value JSONB NOT NULL,
  unit TEXT,
  data_type TEXT NOT NULL,
  min_value DOUBLE PRECISION,
  max_value DOUBLE PRECISION,
  description TEXT,
  UNIQUE (set_id, param_key)
);

CREATE TABLE IF NOT EXISTS parameter_set_events (
  id BIGSERIAL PRIMARY KEY,
  set_id BIGINT NOT NULL REFERENCES parameter_sets(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('create', 'submit', 'approve', 'reject', 'activate', 'archive')),
  actor TEXT NOT NULL,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS parameter_confirmations (
  id BIGSERIAL PRIMARY KEY,
  device_id TEXT NOT NULL,
  device_type TEXT NOT NULL,
  parameter_set_id BIGINT NOT NULL REFERENCES parameter_sets(id) ON DELETE CASCADE,
  parameter_version INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('fetched', 'applied', 'failed')),
  message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW analysis_view AS
SELECT p.barcode, p.device_id, p.processed_at, p.params, i.station_id, i.inspected_at, i.results
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;

-- Experiment management
CREATE TABLE IF NOT EXISTS experiment_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    process_type VARCHAR(100) NOT NULL DEFAULT 'adhesive_curing',
    method VARCHAR(50) NOT NULL,
    factors JSONB NOT NULL,
    design_runs JSONB NOT NULL,
    response_name VARCHAR(100) DEFAULT 'response',
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS experiment_results (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES experiment_plans(id) ON DELETE CASCADE,
    run_order INTEGER NOT NULL,
    response_value DOUBLE PRECISION,
    notes TEXT,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plan_id, run_order)
);
