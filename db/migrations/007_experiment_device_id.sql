-- Add device_id to experiment_results for tracking which device reported each result
ALTER TABLE experiment_results ADD COLUMN IF NOT EXISTS device_id VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_experiment_results_device ON experiment_results(device_id);
