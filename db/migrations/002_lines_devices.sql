CREATE TABLE IF NOT EXISTS production_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  responsible TEXT NOT NULL,
  location TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS device_registry (
  id TEXT PRIMARY KEY,
  line_id UUID REFERENCES production_lines(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  icon TEXT,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO production_lines (name, responsible, location)
VALUES ('默认产线', '管理员', '未分配')
ON CONFLICT (name) DO NOTHING;

INSERT INTO device_registry (id, line_id, name, type, icon, description)
SELECT DISTINCT
  ps.device_id,
  (SELECT id FROM production_lines WHERE name = '默认产线'),
  ps.device_id,
  ps.device_id,
  'Monitor',
  '自动从历史数据回填'
FROM process_summary ps
WHERE NOT EXISTS (SELECT 1 FROM device_registry dr WHERE dr.id = ps.device_id);
