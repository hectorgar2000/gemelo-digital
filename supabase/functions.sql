-- ============================================================
-- Gemelo Digital — Funciones SQL para agregaciones server-side
-- Ejecutar en Supabase → SQL Editor → New query → Run
-- ============================================================

-- 1. Heatmap: demanda media por (semana, hora) para un año
--    p_week_start / p_week_end permiten partir la consulta en dos mitades
--    (1-26 y 27-53) para que cada llamada devuelva < 1000 filas y no choque
--    con el límite max_rows de PostgREST (supabase-js no pagina RPC POST).
CREATE OR REPLACE FUNCTION get_heatmap(
  p_year       INT,
  p_week_start INT DEFAULT 1,
  p_week_end   INT DEFAULT 53
)
RETURNS TABLE(week INT, hour INT, demand FLOAT) AS $$
  SELECT
    EXTRACT(WEEK  FROM ts AT TIME ZONE 'UTC')::INT AS week,
    EXTRACT(HOUR  FROM ts AT TIME ZONE 'UTC')::INT AS hour,
    ROUND(AVG(demand_mw))::FLOAT                   AS demand
  FROM energy
  WHERE ts >= make_timestamptz(p_year, 1, 1, 0, 0, 0, 'UTC')
    AND ts <  make_timestamptz(p_year + 1, 1, 1, 0, 0, 0, 'UTC')
    AND EXTRACT(WEEK FROM ts AT TIME ZONE 'UTC')::INT
        BETWEEN p_week_start AND p_week_end
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


-- 4. Series temporales: rejilla temporal completa con temperatura y demanda
--    Usa generate_series para generar TODOS los buckets del rango, aunque no
--    haya datos en alguno. Los buckets sin datos devuelven NULL en lugar de
--    omitir la fila, lo que permite connectNulls en el frontend.
CREATE OR REPLACE FUNCTION get_series(p_hours INT, p_bucket_minutes INT)
RETURNS TABLE(ts TIMESTAMPTZ, temperature FLOAT, demand FLOAT) AS $$
  WITH
    -- Rejilla temporal completa: un bucket cada p_bucket_minutes desde NOW()-p_hours hasta NOW()
    time_grid AS (
      SELECT
        TO_TIMESTAMP(
          FLOOR(EXTRACT(EPOCH FROM g) / (p_bucket_minutes * 60.0))
          * (p_bucket_minutes * 60)
        )::TIMESTAMPTZ AS bucket
      FROM generate_series(
        NOW() - MAKE_INTERVAL(hours => p_hours),
        NOW(),
        (p_bucket_minutes::TEXT || ' minutes')::INTERVAL
      ) AS g
    ),
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
    tg.bucket                   AS ts,
    w.temperature,
    e.demand
  FROM time_grid tg
  LEFT JOIN w ON w.bucket = tg.bucket
  LEFT JOIN e ON e.bucket = tg.bucket
  ORDER BY tg.bucket;
$$ LANGUAGE SQL STABLE;
