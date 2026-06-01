-- ============================================================
-- Gemelo Digital — Funciones SQL para agregaciones server-side
-- Ejecutar en Supabase → SQL Editor → New query → Run
-- ============================================================

-- 1. Heatmap: demanda media por (semana, hora) para un año
CREATE OR REPLACE FUNCTION get_heatmap(p_year INT)
RETURNS TABLE(week INT, hour INT, demand FLOAT) AS $$
  SELECT
    EXTRACT(WEEK  FROM ts AT TIME ZONE 'UTC')::INT AS week,
    EXTRACT(HOUR  FROM ts AT TIME ZONE 'UTC')::INT AS hour,
    ROUND(AVG(demand_mw))::FLOAT                   AS demand
  FROM energy
  WHERE ts >= make_timestamptz(p_year, 1, 1, 0, 0, 0, 'UTC')
    AND ts <  make_timestamptz(p_year + 1, 1, 1, 0, 0, 0, 'UTC')
  GROUP BY week, hour
  ORDER BY week, hour;
$$ LANGUAGE SQL STABLE;


-- 2. Comparador: demanda media semanal para un año
CREATE OR REPLACE FUNCTION get_weekly_demand(p_year INT)
RETURNS TABLE(week INT, demand FLOAT) AS $$
  SELECT
    EXTRACT(WEEK FROM ts AT TIME ZONE 'UTC')::INT AS week,
    ROUND(AVG(demand_mw))::FLOAT                  AS demand
  FROM energy
  WHERE ts >= make_timestamptz(p_year, 1, 1, 0, 0, 0, 'UTC')
    AND ts <  make_timestamptz(p_year + 1, 1, 1, 0, 0, 0, 'UTC')
  GROUP BY week
  ORDER BY week;
$$ LANGUAGE SQL STABLE;


-- 3. What-if: curva demanda media por banda de temperatura (cada 2°C)
CREATE OR REPLACE FUNCTION get_whatsif_curve(p_months INT DEFAULT 36)
RETURNS TABLE(temp FLOAT, demand FLOAT) AS $$
  SELECT
    FLOOR(w.temperature_c / 2) * 2       AS temp,
    ROUND(AVG(e.demand_mw))::FLOAT        AS demand
  FROM weather w
  JOIN energy  e ON DATE_TRUNC('hour', w.ts) = DATE_TRUNC('hour', e.ts)
  WHERE w.ts >= NOW() - MAKE_INTERVAL(months => p_months)
    AND w.temperature_c IS NOT NULL
  GROUP BY FLOOR(w.temperature_c / 2) * 2
  HAVING COUNT(*) > 5
  ORDER BY temp;
$$ LANGUAGE SQL STABLE;


-- 4. Series temporales: max temperatura y demanda por ventana de tiempo
--    Usa epoch para el bucketing (correcto para cualquier intervalo, incluidos 3h, 12h, 1d)
CREATE OR REPLACE FUNCTION get_series(p_hours INT, p_bucket_minutes INT)
RETURNS TABLE(ts TIMESTAMPTZ, temperature FLOAT, demand FLOAT) AS $$
  WITH
    w AS (
      SELECT
        TO_TIMESTAMP(
          FLOOR(EXTRACT(EPOCH FROM wt.ts) / (p_bucket_minutes * 60.0))
          * (p_bucket_minutes * 60)
        )::TIMESTAMPTZ AS bucket,
        MAX(wt.temperature_c) AS temperature
      FROM weather wt
      WHERE wt.ts >= NOW() - MAKE_INTERVAL(hours => p_hours)
      GROUP BY bucket
    ),
    e AS (
      SELECT
        TO_TIMESTAMP(
          FLOOR(EXTRACT(EPOCH FROM et.ts) / (p_bucket_minutes * 60.0))
          * (p_bucket_minutes * 60)
        )::TIMESTAMPTZ AS bucket,
        MAX(et.demand_mw) AS demand
      FROM energy et
      WHERE et.ts >= NOW() - MAKE_INTERVAL(hours => p_hours)
      GROUP BY bucket
    )
  SELECT
    COALESCE(w.bucket, e.bucket) AS ts,
    w.temperature,
    e.demand
  FROM w FULL OUTER JOIN e ON w.bucket = e.bucket
  ORDER BY ts;
$$ LANGUAGE SQL STABLE;
