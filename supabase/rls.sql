-- ============================================================
-- Gemelo Digital — Row Level Security (RLS)
-- Ejecutar en Supabase → SQL Editor → New query → Run
--
-- ANTES de aplicar este archivo:
--   1. Obtener la clave anon en Supabase:
--      Project Settings → API → anon public
--   2. Añadirla a web/.env.local como SUPABASE_ANON_KEY=<clave>
--   3. Añadirla en Vercel como variable de entorno SUPABASE_ANON_KEY
--
-- DESPUÉS de aplicar:
--   - El frontend (API Routes de Next.js) usa la clave anon (solo lectura)
--   - Los scripts Python siguen usando SUPABASE_SERVICE_KEY (lectura+escritura)
--     porque service_role bypasea RLS por definición
-- ============================================================

-- 1. Activar RLS en todas las tablas
ALTER TABLE weather   ENABLE ROW LEVEL SECURITY;
ALTER TABLE energy    ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast  ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;

-- 2. Políticas de solo lectura para el rol anon (frontend web)
--    USING (true) = cualquier fila es accesible para SELECT
CREATE POLICY "anon_read_weather"
  ON weather   FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_energy"
  ON energy    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_forecast"
  ON forecast  FOR SELECT TO anon USING (true);

CREATE POLICY "anon_read_anomalies"
  ON anomalies FOR SELECT TO anon USING (true);

-- 3. Negar explícitamente escritura al rol anon (redundante con RLS activado,
--    pero hace la intención explícita en el SQL del proyecto)
--    No es necesario crear políticas DENY en PostgreSQL: la ausencia de
--    una política FOR INSERT/UPDATE/DELETE ya deniega esa operación.

-- Verificar que las políticas se han creado:
SELECT schemaname, tablename, policyname, roles, cmd
FROM pg_policies
WHERE tablename IN ('weather', 'energy', 'forecast', 'anomalies')
ORDER BY tablename, cmd;
