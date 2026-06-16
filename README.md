# Gemelo Digital — Energía & Clima

Dashboard en tiempo real de demanda eléctrica peninsular española y condiciones meteorológicas en Madrid. Incluye predicción con Prophet, detección de anomalías y comparativa interanual.

## Demo

> Dashboard desplegado en Vercel · Datos actualizados cada hora vía GitHub Actions

---

## Arquitectura

```
Open-Meteo API          REE API pública
     │                       │
     └──────────┬────────────┘
                │  (cada hora)
         cloud_collector.py
                │
                ▼
          Supabase (PostgreSQL)
         ┌──────┴──────────────────────────┐
         │  weather · energy · forecast · anomalies  │
         └──────┬──────────────────────────┘
                │
      ┌─────────┼──────────────┐
      │         │              │
  Next.js    Prophet        IsolationForest
  (Vercel)  (diario)        (semanal)
```

### Flujo de datos

1. **Ingesta horaria** — `cloud_collector.py` descarga clima (Open-Meteo) y demanda (REE) con estrategia *watermark*: consulta el último timestamp en Supabase y pide exactamente el rango que falta, sin huecos.
2. **Predicción diaria** — `cloud_forecast.py` carga el modelo Prophet serializado y genera 36h de predicción de demanda con intervalos de confianza al 95%.
3. **Anomalías semanales** — `cloud_anomaly.py` detecta anomalías combinando Z-score sobre residuos Prophet + Isolation Forest con features de temperatura y hora local Madrid.
4. **Evaluación diaria** — `cloud_model_eval.py` compara forecast vs real y alerta si MAPE > 10%.
5. **Reentrenamiento mensual** — `cloud_retrain.py` reentrena Prophet con los últimos 12 meses y commitea el nuevo `.pkl` al repositorio.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Frontend** | Next.js 15 (App Router) · TypeScript · Tailwind CSS · Recharts |
| **Backend API** | Next.js API Routes (serverless) |
| **Base de datos** | Supabase (PostgreSQL) con RLS habilitado |
| **ML / Predicción** | Prophet (regresión con temperatura como regresor) |
| **Anomalías** | Z-score + IsolationForest (scikit-learn) |
| **Ingesta** | Python · httpx · Open-Meteo API · REE API pública |
| **Automatización** | GitHub Actions (6 workflows) |
| **Despliegue web** | Vercel |
| **Seguridad** | Rate limiting · CSP headers · HSTS · RLS Supabase |

---

## Funcionalidades

### Dashboard principal
- **KPIs en tiempo real** — demanda MW, temperatura, radiación solar, humedad, viento
- **Gráfico demanda + temperatura** — últimas 24h / 7d / 30d / 1 año con ventana configurable
- **Predicción Prophet** — últimas 48h reales + próximas 24h estimadas con banda de confianza
- **Anomalías detectadas** — listado con nivel de confianza (alta / media) y Z-score
- **Badge ⚠ Estimado** — se muestra cuando hay datos sintéticos por indisponibilidad de REE

### Explorador de patrones
- **Heatmap hora × semana** — patrón de demanda anual con escala p5–p95
- **Simulador What-If** — slider de temperatura → demanda estimada según curva en U histórica

### Comparador interanual
- Demanda media semanal de hasta 5 años superpuestos
- Exportación CSV (7d / 30d / 1 año) con clima + demanda + anomalías

---

## GitHub Actions

| Workflow | Frecuencia | Qué hace |
|---|---|---|
| `hourly_collect.yml` | Cada hora (:10) | Descarga clima y demanda, escribe en Supabase |
| `daily_forecast.yml` | 05:30 UTC | Genera predicción Prophet 36h |
| `weekly_anomaly.yml` | Lunes 06:00 UTC | Detecta anomalías últimas 2 semanas |
| `daily_model_eval.yml` | 07:00 UTC | Evalúa MAPE del forecast; alerta si > 10% |
| `monitor_ingesta.yml` | Cada 3h | Alerta si datos llevan > 5h sin actualizarse |
| `monthly_retrain.yml` | Día 1 de cada mes | Reentrena Prophet con 12 meses y commitea el pkl |

---

## Estructura del proyecto

```
gemelo_digital/
├── .github/workflows/        # 6 workflows de automatización
├── ingestion/
│   ├── openmeteo.py          # Cliente Open-Meteo (clima actual e histórico)
│   ├── ree.py                # Cliente REE API pública (demanda + sintético)
│   ├── supabase_writer.py    # Upsert por ts en las 4 tablas
│   └── validators.py         # Validación de rangos físicos
├── prediction/
│   ├── forecast.py           # Entrenamiento y predicción local
│   ├── anomaly_detector.py   # Detección local
│   └── prophet_model.pkl     # Modelo serializado (se actualiza mensualmente)
├── supabase/
│   ├── schema.sql            # Definición de tablas e índices
│   ├── rls.sql               # Políticas Row Level Security
│   └── functions.sql         # Funciones SQL (heatmap, series, what-if…)
├── web/                      # Next.js app
│   └── src/
│       ├── app/              # Pages y API routes
│       ├── components/       # DemandChart, ForecastChart, HeatmapGrid…
│       └── lib/supabase.ts   # Cliente Supabase (anon key con RLS)
├── cloud_collector.py        # Colector para GitHub Actions
├── cloud_forecast.py         # Predicción para GitHub Actions
├── cloud_anomaly.py          # Anomalías para GitHub Actions
├── cloud_model_eval.py       # Evaluación MAPE para GitHub Actions
├── cloud_retrain.py          # Reentrenamiento mensual para GitHub Actions
├── monitor_ingesta.py        # Monitor de frescura de datos
└── requirements.txt          # Dependencias Python pineadas
```

---

## Configuración local

### Requisitos
- Python 3.11+
- Node.js 20+
- Cuenta Supabase (plan gratuito suficiente)

### Variables de entorno

**Python** — crear `.env` en la raíz:
```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   # service_role key (server-side only)
```

**Next.js** — crear `web/.env.local`:
```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...      # anon/public key (lectura con RLS)
```

### Instalación

```bash
# Python
pip install -r requirements.txt

# Next.js
cd web && npm install
```

### Base de datos

1. Crear proyecto en [supabase.com](https://supabase.com)
2. Ejecutar en SQL Editor → `supabase/schema.sql`
3. Ejecutar → `supabase/rls.sql` (activa RLS + políticas de lectura pública)
4. Ejecutar → `supabase/functions.sql` (funciones para heatmap, series, what-if)

### Desarrollo

```bash
# Recoger datos manualmente
python cloud_collector.py

# Iniciar dashboard
cd web && npm run dev   # http://localhost:3000
```

---

## Despliegue en producción

### Vercel

1. Importar el repositorio en [vercel.com](https://vercel.com)
2. Establecer directorio raíz: `web/`
3. Añadir variables de entorno: `SUPABASE_URL` y `SUPABASE_ANON_KEY`

### GitHub Actions

Añadir en Settings → Secrets and variables → Actions:

| Secret | Descripción |
|---|---|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_SERVICE_KEY` | service_role key (solo server-side, nunca en el cliente) |

---

## Seguridad

- **RLS habilitado** en las 4 tablas de Supabase — el cliente web usa la `anon key` (solo SELECT)
- **`SUPABASE_SERVICE_KEY` nunca en el cliente** — solo en GitHub Secrets y API routes server-side
- **Rate limiting** en todas las rutas API (60 req/min general, 10 req/min para export)
- **Security headers** — CSP, HSTS, X-Frame-Options, Permissions-Policy
- **Dependencias pineadas** en workflows para evitar incompatibilidades de versión

---

## Datos

- **Clima**: [Open-Meteo](https://open-meteo.com/) — ERA5 reanalysis + forecast API. Sin registro, sin límite de uso razonable.
- **Demanda eléctrica**: [API pública de REE](https://apidatos.ree.es/) — Red Eléctrica de España. Sin token requerido.
- **Cobertura temporal**: desde 2016 hasta hoy (datos históricos backfilled + ingesta continua)
- **Granularidad**: horaria

---

## Licencia

MIT
