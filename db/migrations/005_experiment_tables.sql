-- Experiment management tables
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

CREATE INDEX IF NOT EXISTS idx_experiment_results_plan ON experiment_results(plan_id);
