ALTER TABLE process_summary ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
ALTER TABLE inspection_results ADD COLUMN product_model TEXT NOT NULL DEFAULT '';
DROP VIEW IF EXISTS analysis_view;
CREATE VIEW analysis_view AS
SELECT
  p.barcode,
  p.device_id,
  p.processed_at,
  p.params,
  p.product_model AS process_product_model,
  i.station_id,
  i.inspected_at,
  i.results,
  i.product_model AS inspection_product_model
FROM process_summary p
LEFT JOIN inspection_results i ON i.barcode = p.barcode;
