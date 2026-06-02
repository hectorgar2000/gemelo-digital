# Gemelo Digital — Energía vs Clima

**Última actualización:** 2026-06-02  
**Estado general:** Fase 8 completada ✅ — Proyecto en producción (Vercel + Supabase + GitHub Actions)

---

## Objetivo del proyecto

Construir un gemelo digital que correlacione el consumo eléctrico de España (datos REE) con las condiciones meteorológicas (Open-Meteo) para identificar patrones, detectar anomalías y predecir la demanda en función del clima.

Proyecto de aprendizaje con fines prácticos: dominar el stack de datos IoT/sensores antes de un proyecto real.

---

## Fuentes de datos

| Fuente | Qué aporta | URL base | Auth |
|--------|-----------|----------|------|
| **REE apidatos** | Demanda real peninsular (MW), prevista y programada | `https://apidatos.ree.es/es/datos` | **Sin key — API pública** |
| **Open-Meteo ERA5** | Temperatura, viento, humedad, nubosidad, radiación solar | `https://api.open-meteo.com/v1/forecast` + `/archive` | Sin key |

**Fuente de energía:** `apidatos.ree.es/es/datos/demanda/demanda-tiempo-real` — resolución 10 min, histórico desde ~2019.  
**Fallback energía:** `ingestion/ree.py` incluye `fetch_demand_synthetic()` si la API REE falla.  
**Clima histórico:** Open-Meteo ERA5 archive (hasta 2–3 días de lag sobre la fecha actual).

---

## Stack tecnológico actual (producción)

```
Open-Meteo ──┐
             ├──► Python (ingestión) ──► Supabase (PostgreSQL) ──► Next.js (Vercel)
REE API    ──┘        │
                      └──► GitHub Actions (cron horario)
```

| Capa | Herramienta | Notas |
|------|------------|-------|
| Lenguaje | Python 3.11+ | ingestión + predicción |
| Base de datos cloud | **Supabase** (PostgreSQL) | tablas: weather, energy, forecast, anomalies |
| Frontend | **Next.js 15** + Tailwind + Recharts | desplegado en Vercel |
| Automatización cloud | **GitHub Actions** | cron cada hora a :10 min |
| Forecasting | Prophet (Meta) | modelo `.pkl` en repo |
| Análisis local | pandas, numpy, matplotlib | Jupyter notebooks |
| Base de datos local (legacy) | InfluxDB 2.x | aún funciona para desarrollo local |
| Visualización local (legacy) | Grafana | dashboards locales, no en producción |

**URLs de producción:**
- App web: `https://gemelo-digital.vercel.app` (o dominio configurado en Vercel)
- Base de datos: proyecto Supabase (ver `.env`)

---

## Esquema de base de datos (Supabase / PostgreSQL)

```sql
-- Datos meteorológicos (Open-Meteo)
weather (
  ts                   TIMESTAMPTZ PRIMARY KEY,
  temperature_c        FLOAT,
  humidity_pct         FLOAT,
  wind_speed_kmh       FLOAT,
  cloud_cover_pct      FLOAT,
  solar_radiation_wm2  FLOAT
)

-- Demanda eléctrica (REE API pública)
energy (
  ts         TIMESTAMPTZ PRIMARY KEY,
  demand_mw  FLOAT NOT NULL,
  source     TEXT  -- 'ree_real' | 'synthetic'
)

-- Predicciones Prophet (24h adelante)
forecast (
  ts               TIMESTAMPTZ PRIMARY KEY,
  demand_mw        FLOAT,
  demand_mw_upper  FLOAT,
  demand_mw_lower  FLOAT,
  model            TEXT  -- 'prophet_v1'
)

-- Anomalías detectadas (Z-score + Isolation Forest)
anomalies (
  ts             TIMESTAMPTZ PRIMARY KEY,
  residual_mw    FLOAT,
  z_score        FLOAT,
  iforest_score  FLOAT,
  is_anomaly     INT,
  nivel          TEXT  -- 'alta' | 'media' | 'normal'
)
```

### Funciones SQL (Supabase → SQL Editor → `supabase/functions.sql`)

| Función | Uso |
|---------|-----|
| `get_heatmap(p_year)` | Demanda media por (semana, hora) — heatmap |
| `get_weekly_demand(p_year)` | Demanda media semanal — comparador interanual |
| `get_whatsif_curve(p_months)` | Curva demanda por banda de temperatura |
| `get_series(p_hours, p_bucket_minutes)` | Serie temporal clima+energía con bucket por epoch |

> ⚠️ Si la base de datos se reinicia o migra, re-ejecutar `supabase/functions.sql` completo en el SQL Editor.

---

## Estructura del proyecto

```
gemelo_digital/
├── CONTEXT.md                        ← este archivo
├── requirements.txt                  ← dependencias Python
├── collector.py                      ← colector local (InfluxDB + Supabase dual-write)
├── cloud_collector.py                ← colector cloud (solo Supabase, para GitHub Actions)
├── .github/
│   └── workflows/
│       └── hourly_collect.yml        ← cron GitHub Actions (cada hora)
├── ingestion/
│   ├── openmeteo.py                  ← fetch clima actual e histórico (Open-Meteo)
│   ├── ree.py                        ← fetch demanda REE API pública + sintético
│   ├── influx_writer.py              ← escritura InfluxDB (local)
│   └── supabase_writer.py            ← escritura Supabase (cloud) — upsert en 4 tablas
├── prediction/
│   ├── forecast.py                   ← Prophet local (lee InfluxDB, escribe en ambos)
│   ├── anomaly_detector.py           ← Z-score + Isolation Forest (lee InfluxDB)
│   └── prophet_model.pkl             ← modelo serializado (en repo)
├── supabase/
│   └── functions.sql                 ← funciones SQL de agregación server-side
├── analysis/
│   ├── data_loader.py                ← carga datos de InfluxDB para análisis local
│   ├── 01_exploratory.ipynb
│   ├── 02_correlation.ipynb
│   ├── 03_forecasting.ipynb
│   └── 04_anomaly.ipynb
└── web/                              ← Next.js app (Vercel)
    └── src/
        ├── app/
        │   ├── page.tsx              ← Dashboard principal
        │   ├── explorador/page.tsx   ← Heatmap + What-If
        │   ├── comparar/page.tsx     ← Comparador interanual + Export CSV
        │   └── api/
        │       ├── kpi/route.ts      ← últimos valores clima+energía
        │       ├── series/route.ts   ← serie temporal (get_series SQL)
        │       ├── heatmap/route.ts  ← heatmap paginated (2×PostgREST requests)
        │       ├── whatsif/route.ts  ← curva U temperatura-demanda
        │       ├── compare/route.ts  ← comparador interanual
        │       ├── forecast/route.ts ← predicción Prophet 24h
        │       ├── anomalies/route.ts← anomalías detectadas
        │       └── export/route.ts   ← descarga CSV
        ├── components/
        │   ├── NavBar.tsx
        │   ├── KpiCard.tsx
        │   ├── DemandChart.tsx       ← gráfico demanda+temperatura (24h/7d/30d/1año)
        │   ├── ForecastChart.tsx     ← forecast Prophet vs real
        │   ├── AnomalyList.tsx       ← lista de anomalías por período
        │   ├── HeatmapGrid.tsx       ← heatmap hora×semana
        │   ├── WhatIfSimulator.tsx   ← simulador what-if por temperatura
        │   └── YearCompare.tsx       ← comparador interanual
        └── lib/
            └── supabase.ts           ← cliente Supabase + tipos
```

---

## Roadmap

### Fase 0 — Planificación ✅
- [x] Definir objetivo, APIs, stack

### Fase 1 — Entorno y conexiones ✅
- [x] venv Python, conexión Open-Meteo, módulo REE
- [x] InfluxDB v2.9.1 local, Grafana conectado

### Fase 2 — Pipeline de ingestión ✅
- [x] `ingestion/openmeteo.py`, `ree.py`, `influx_writer.py`
- [x] `collector.py` con `--once` y `--backfill N`

### Fase 3 — Análisis exploratorio ✅
- [x] `01_exploratory.ipynb`, `02_correlation.ipynb`
- [x] Correlaciones Pearson, perfiles horarios/semanales

### Fase 4 — Visualización en Grafana ✅ (legacy local)
- [x] Dashboards: energia-001, clima-001, combinado-001
- [x] Alerta demanda > 33.000 MW

### Fase 5 — Modelo predictivo ✅
- [x] Prophet con temperatura como regresor, estacionalidad múltiple
- [x] `prediction/forecast.py` — predice 24h y escribe en InfluxDB + Supabase
- [x] Modelo guardado en `prediction/prophet_model.pkl`

### Fase 6 — Detección de anomalías ✅
- [x] Z-score sobre residuos Prophet + Isolation Forest (2 métodos combinados)
- [x] `prediction/anomaly_detector.py` — niveles alta/media/normal
- [x] Escribe en InfluxDB + Supabase tabla `anomalies`

### Fase 7 — Migración a Supabase + despliegue Vercel ✅
- [x] Tablas Supabase: `weather`, `energy`, `forecast`, `anomalies`
- [x] `ingestion/supabase_writer.py` con upsert idempotente
- [x] Funciones SQL server-side en `supabase/functions.sql`
- [x] App Next.js con 3 páginas, 8 componentes, 8 rutas API
- [x] Desplegada en Vercel con variables de entorno `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`
- [x] `collector.py` con dual-write (InfluxDB local + Supabase cloud)
- [x] Backfill histórico: ~8.700h de clima real + energía REE (Oct 2025 – Jun 2026)

### Fase 8 — Automatización cloud ✅
- [x] `cloud_collector.py` — colector ligero para entornos sin InfluxDB
- [x] `.github/workflows/hourly_collect.yml` — cron cada hora (`:10 min`)
- [x] GitHub Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` en el repo

---

## Bugs resueltos en producción

| Bug | Causa raíz | Fix aplicado |
|-----|-----------|-------------|
| Heatmap cortado en semana 42 | PostgREST `max_rows=1000` | 2 requests paralelos `.range(0,999)` + `.range(1000,1499)` |
| Colores invisibles semanas 43-52 | Escala p5-p95 genera `t < 0` → `hsl(..., -20%)` = negro | `Math.max(0, Math.min(1, t))` en `demandColor()` |
| Saltos en gráfico 30d | Bucketing por `DATE_TRUNC` no funciona para 3h/12h/1d | Reescritura con `FLOOR(EPOCH / bucket_sec)` |
| What-If -4°C < 20°C | Datos escasos en extremos generan ruido | Enforcement monotonicity U-shape desde mínimo hacia extremos |
| REE API 400 en chunks de 30d | Algunos rangos de fechas dan HTTP 400 | `chunk_days=7` en backfill |
| TypeScript error `sb.rpc(...)` | supabase-js no conoce funciones custom | Cast `(sb.rpc as Function)(...)` |

---

## Variables de entorno

### `.env` (local — nunca commitear)
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   # service_role key — SOLO server-side
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=...
INFLUX_ORG=gemelo
INFLUX_BUCKET=gemelo_digital
```

### `web/.env.local` (Vercel — nunca commitear)
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

### GitHub Secrets (para Actions)
```
SUPABASE_URL
SUPABASE_SERVICE_KEY
```

> 🔒 La `SUPABASE_SERVICE_KEY` es la clave `service_role` — tiene acceso completo sin RLS. **Nunca exponerla en el cliente (browser).** Usarla solo en server-side: API routes de Next.js, GitHub Actions, scripts Python.

---

## Comandos útiles

```bash
# Colector local (bucle infinito, cada 10 min)
python collector.py

# Colector una vez
python collector.py --once

# Backfill últimas N horas
python collector.py --backfill 720   # 30 días

# Predicción local (carga prophet_model.pkl, escribe forecast en Supabase)
python prediction/forecast.py

# Reentrenar modelo Prophet (requiere InfluxDB local con datos)
python prediction/forecast.py --retrain

# Detección de anomalías local
python prediction/anomaly_detector.py --hours 168 --report

# Colector cloud (solo Supabase, sin InfluxDB)
python cloud_collector.py
```

---

## Decisiones técnicas

| Decisión | Razón |
|----------|-------|
| Supabase sobre InfluxDB en producción | PostgreSQL estándar, APIs REST nativas, hosting gratuito en cloud |
| Funciones SQL server-side | Evitan límite `max_rows=1000` de PostgREST y reducen tráfico |
| ISR (revalidate=3600) en heatmap/compare | Son datos históricos que no cambian cada minuto |
| `force-dynamic` en kpi/forecast/anomalies | Datos que deben ser siempre frescos |
| p5-p95 en escala heatmap | Evita que picos de invierno/verano compriman los colores intermedios |
| `(sb.rpc as Function)(...)` | supabase-js TypeScript no infiere nombres de funciones custom |
| 2 requests paginados en heatmap | PostgREST ignora Range > 1000 aunque el header lo pida |
| chunk_days=7 en backfill REE | API REE da HTTP 400 en algunos rangos de 30d; 7d siempre funciona |

---

## Notas y aprendizajes

- **PostgREST max_rows=1000**: límite en el servidor que no se puede sobrepasar con un solo request `.range(0, N)`. Solución: 2 requests paralelos con rangos complementarios.
- **HSL lightness negativa**: `hsl(220, 80%, -20%)` se renderiza como negro en todos los navegadores. Con escala p5-p95 los valores por debajo del p5 generan `t < 0`. Fix: `Math.max(0, Math.min(1, t))`.
- **ERA5 archive lag**: Open-Meteo tiene 2-3 días de retraso en datos históricos. Los últimos días de temperatura aparecerán vacíos hasta que el archivo se actualice.
- **supabase-py upsert**: `on_conflict="ts"` requiere que `ts` sea PRIMARY KEY o tenga un índice UNIQUE en la tabla.
- **GitHub Actions secrets**: se configuran en Settings → Secrets → Actions del repositorio. No se pueden leer desde la UI, solo comprobar si existen.
- **Vercel ISR**: el primer request tras un deploy o tras expirar el TTL (3600s) regenera la página. Los deploys posteriores invalidan el caché automáticamente.
- **Prophet en serverless**: el modelo `.pkl` está en el repo (~50MB). No se puede ejecutar Prophet en Vercel (límite de tiempo 30s). El forecast se genera localmente o en GitHub Actions y se persiste en Supabase.

---

## Historial de fases

| Fecha | Fase | Notas |
|-------|------|-------|
| 2026-05-26 | Fase 0 | Roadmap y contexto |
| 2026-05-26 | Fase 1 | venv, Open-Meteo, REE, InfluxDB, Grafana |
| 2026-05-26 | Fase 2 | influx_writer, collector |
| 2026-05-26 | Fase 3 | Notebooks análisis exploratorio |
| 2026-05-26 | Fase 4 | Dashboards Grafana + alertas |
| 2026-05-26 | Fase 5 | Prophet forecast 24h |
| 2026-05-27 | Fase 6 | Z-score + Isolation Forest anomalías |
| 2026-06-01 | Fase 7 | Migración Supabase, app Next.js, Vercel |
| 2026-06-02 | Fase 8 | GitHub Actions cron, cloud_collector, backfill histórico |
