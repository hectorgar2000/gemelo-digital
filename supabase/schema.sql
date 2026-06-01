-- ============================================================
-- Gemelo Digital — Schema Supabase (PostgreSQL)
-- Ejecutar en Supabase → SQL Editor → New query → Run
-- ============================================================

-- Tabla de datos meteorológicos (Open-Meteo ERA5)
CREATE TABLE IF NOT EXISTS weather (
  ts                   TIMESTAMPTZ NOT NULL,
  temperature_c        FLOAT,
  humidity_pct         FLOAT,
  wind_speed_kmh       FLOAT,
  cloud_cover_pct      FLOAT,
  solar_radiation_wm2  FLOAT,
  PRIMARY KEY (ts)
);

-- Tabla de demanda eléctrica (REE API pública)
CREATE TABLE IF NOT EXISTS energy (
  ts         TIMESTAMPTZ NOT NULL,
  demand_mw  FLOAT       NOT NULL,
  source     TEXT        DEFAULT 'ree_real',
  PRIMARY KEY (ts)
);

-- Tabla de predicciones Prophet
CREATE TABLE IF NOT EXISTS forecast (
  ts               TIMESTAMPTZ NOT NULL,
  demand_mw        FLOAT,
  demand_mw_upper  FLOAT,
  demand_mw_lower  FLOAT,
  model            TEXT DEFAULT 'prophet_v1',
  PRIMARY KEY (ts)
);

-- Tabla de anomalías detectadas
CREATE TABLE IF NOT EXISTS anomalies (
  ts             TIMESTAMPTZ NOT NULL,
  residual_mw    FLOAT,
  z_score        FLOAT,
  iforest_score  FLOAT,
  is_anomaly     INTEGER DEFAULT 0,
  nivel          TEXT    DEFAULT 'normal',
  PRIMARY KEY (ts)
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_weather_ts    ON weather  (ts DESC);
CREATE INDEX IF NOT EXISTS idx_energy_ts     ON energy   (ts DESC);
CREATE INDEX IF NOT EXISTS idx_forecast_ts   ON forecast (ts DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_ts  ON anomalies(ts DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_nivel ON anomalies(nivel, ts DESC);

-- Políticas de acceso: la service_role key puede leer y escribir todo
-- (por defecto en Supabase con RLS desactivado esto ya funciona)
