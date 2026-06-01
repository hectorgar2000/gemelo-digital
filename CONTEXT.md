# Gemelo Digital — Energía vs Clima

**Última actualización:** 2026-05-27  
**Estado general:** Fase 6 completada ✅ — Proyecto completo (todas las fases terminadas)

---

## Objetivo del proyecto

Construir un gemelo digital que correlacione el consumo eléctrico de España (datos REE) con las condiciones meteorológicas (Open-Meteo) para identificar patrones, detectar anomalías y predecir la demanda en función del clima.

Proyecto de aprendizaje con fines prácticos: dominar el stack de datos IoT/sensores antes de un proyecto real.

---

## Fuentes de datos

| Fuente | Qué aporta | URL base | Auth |
|--------|-----------|----------|------|
| **REE apidatos** | Demanda real peninsular (MW), prevista y programada | `https://apidatos.ree.es/es/datos` | **Sin key — API pública** |
| **ESIOS (REE)** | Precio mercado, generación por tecnología (extra) | `https://api.esios.ree.es` | Token gratuito opcional (email a analisis.sistedataesios@ree.es) |
| **Open-Meteo** | Temperatura, viento, humedad, nubosidad, radiación solar | `https://api.open-meteo.com/v1/forecast` | Sin key |

**Fuente de energía:** `apidatos.ree.es/es/datos/demanda/demanda-tiempo-real` — API pública sin token, resolución 5 min, histórico desde ~2019.  
**Fallback:** `ingestion/ree.py` incluye `fetch_demand_synthetic()` como fallback si la API REE falla.

---

## Stack tecnológico

```
Open-Meteo  ──┐
              ├──► Python (ingestión) ──► InfluxDB ──► Grafana
REE API     ──┘         │
                        └──► Jupyter / pandas (análisis)
```

| Capa | Herramienta | Versión objetivo |
|------|------------|-----------------|
| Lenguaje | Python | 3.11+ |
| Ingestión | `httpx` + `schedule` | - |
| Base de datos | InfluxDB | 2.x (OSS) |
| Visualización | Grafana | 10.x |
| Análisis | pandas, numpy, matplotlib | - |
| Forecasting | Prophet (Meta) | - |

---

## Roadmap

### Fase 0 — Planificación ✅
- [x] Definir objetivo del proyecto
- [x] Seleccionar APIs y stack tecnológico
- [x] Crear archivo de contexto

---

### Fase 1 — Entorno y conexiones ⏳
- [x] **1.1** Crear entorno virtual Python (`venv`) e instalar dependencias base
- [x] **1.2** Verificar conexión con Open-Meteo — devuelve datos reales correctamente
- [x] **1.3** Módulo REE listo — usa ESIOS API (token gratuito) + fallback sintético funcional
- [x] **1.4** InfluxDB v2.9.1 corriendo en `C:\Users\Admin\influxdb2\` → `http://localhost:8086` — bucket `gemelo_digital` OK
- [x] **1.5** Grafana corriendo en `http://localhost:3000` — datasource `InfluxDB_GemeloDigital` conectado y verificado (query Flux devuelve buckets)

---

### Fase 2 — Pipeline de ingestión ✅
- [x] **2.1** Módulo `ingestion/openmeteo.py` — temperatura, humedad, viento, nubosidad, radiación solar (Madrid)
- [x] **2.2** Módulo `ingestion/ree.py` — demanda eléctrica via ESIOS + fallback sintético
- [x] **2.3** Módulo `ingestion/influx_writer.py` — measurements `weather` y `energy` con tags y WritePrecision.S
- [x] **2.4** Script `collector.py` — scheduler 10min + modos `--once` y `--backfill N`
- [x] **2.5** Verificado: 250 puntos weather + 49 puntos energy en InfluxDB. Backfill 48h OK

---

### Fase 3 — Análisis exploratorio ✅
- [x] **3.1** `analysis/01_exploratory.ipynb` — stats, 0 nulos, 6 gráficos (series + distribuciones)
- [x] **3.2** `analysis/02_correlation.ipynb` — matriz correlación Pearson, scatter clima-demanda
- [x] **3.3** Ranking de impacto generado (`02_ranking_impacto.png`)
- [x] **3.4** Perfil horario y semanal (`02_perfil_horario.png`, `02_perfil_semanal.png`)

---

### Fase 4 — Visualización en Grafana ✅
- [x] **4.1** Dashboard `energia-001` — gauge actual + stats 24h + series 24h y 7d
- [x] **4.2** Dashboard `clima-001` — 4 stats actuales + 4 series temporales 24h
- [x] **4.3** Dashboard `combinado-001` — Temp+Demanda (doble eje), Solar+Demanda, perfil horario
- [x] **4.4** Alerta `uid=bfn818tr3kdfke` — demanda > 33.000 MW durante 5 min → Alerting → Alert rules

---

### Fase 5 — Modelo predictivo ✅
- [x] **5.1** `analysis/03_forecasting.ipynb` — Prophet con temperatura como regresor, train/test split, componentes
- [x] **5.2** Evaluación MAE/RMSE/MAPE — baseline vs modelo con temperatura, análisis de errores por hora y día
- [x] **5.3** `prediction/forecast.py` — carga modelo pkl, obtiene pronóstico Open-Meteo, predice y escribe en InfluxDB (measurement: forecast)
- [x] **5.4** Panel "Demanda real vs Prediccion Prophet" añadido al dashboard energia-001 en Grafana

---

### Fase 6 — Detección de anomalías ✅
- [x] **6.1** Definir qué es una anomalía: demanda inesperadamente alta/baja dado el contexto climático (residuo Prophet)
- [x] **6.2** `analysis/04_anomaly.ipynb` — Z-score (|Z|>2.5) + Isolation Forest (contamination=2%). Niveles: alta (ambos) / media (uno) / normal. Top 10 anomalías. Escribe measurement `anomalies` en InfluxDB.
- [x] **6.3** `prediction/anomaly_detector.py` — módulo producción CLI. Escribe `anomalies` en InfluxDB. Panel "Anomalias detectadas" añadido al dashboard energia-001 en Grafana.

---

## Estructura de directorios objetivo

```
gemelo_digital/
├── CONTEXT.md                  ← este archivo
├── requirements.txt
├── collector.py                ← script principal de ingestión
├── ingestion/
│   ├── __init__.py
│   ├── openmeteo.py
│   ├── ree.py
│   └── influx_writer.py
├── prediction/
│   ├── forecast.py             ← predicción 24h con Prophet
│   ├── anomaly_detector.py     ← detección de anomalías (Z-score + Isolation Forest)
│   └── prophet_model.pkl       ← modelo serializado
└── analysis/
    ├── data_loader.py
    ├── 01_exploratory.ipynb
    ├── 02_correlation.ipynb
    ├── 03_forecasting.ipynb
    └── 04_anomaly.ipynb        ← análisis de anomalías
```

---

## Decisiones técnicas tomadas

| Decisión | Razón |
|----------|-------|
| InfluxDB sobre PostgreSQL | Serie temporal nativa, mejor rendimiento para lecturas de sensor frecuentes |
| Open-Meteo sobre OpenWeatherMap | Sin API key, sin límite, datos de alta resolución temporal |
| ESIOS sobre apidatos.ree.es | apidatos devuelve 500 sistemáticamente; ESIOS es la API oficial más estable (requiere token gratuito) |
| Prophet para forecasting | Maneja estacionalidad múltiple (diaria + semanal) y regresores externos con poco código |

---

## Notas y aprendizajes

- `apidatos.ree.es` (documentado en tutoriales 2022-2024) devuelve 500 en todos los endpoints. Se sustituyó por la API ESIOS oficial.
- `ingestion/ree.py` tiene doble modo: datos reales vía ESIOS si hay token en `.env`, y datos sintéticos realistas si no hay token. Esto permite continuar el desarrollo en paralelo mientras se espera el token.
- Open-Meteo no tiene límite de llamadas y no requiere registro. Ideal para prototipado.
- El `.env` tiene las variables `ESIOS_TOKEN`, `INFLUX_TOKEN`, `INFLUX_URL`, `INFLUX_ORG`, `INFLUX_BUCKET`.
- `WritePrecision` en influxdb-client usa `S` (no `SECONDS`) para segundos.
- `collector.py --backfill 8760` rellena 365 días. Energía generada con `generate_demand_from_weather_records()` correlacionada con temperatura real.
- `WritePrecision.S` (no SECONDS). Exponentes no enteros con base negativa dan `complex` en Python — usar ramas if/elif.
- Prophet requiere columnas `ds` (datetime sin tz) e `y`. Los regresores deben estar disponibles también en el futuro (usar Open-Meteo forecast).
- Modelo serializado en `prediction/prophet_model.pkl`. Reentrenar con `python prediction/forecast.py --retrain`.
- Measurement `forecast` en InfluxDB: campos `demand_mw`, `demand_mw_lower`, `demand_mw_upper`, tag `model=prophet_v1`.
- Measurement `anomalies` en InfluxDB: campos `residual_mw`, `z_score`, `iforest_score`, `is_anomaly`; tags `nivel` (alta/media/normal), `region=peninsular`.
- Anomalía "alta confianza": Z-score Y Isolation Forest coinciden. "media": solo uno. Umbral Z: |Z|>2.5. Contamination IF: 2%.
- `python prediction/anomaly_detector.py --hours 8760 --report` para análisis completo de 1 año.
- **Colector en producción**: `python collector.py` (sin flags) recolecta cada 10 min. Ejecutar en ventana PowerShell separada para mantener datos frescos en Grafana.
- **Stat panel solar radiation** muestra el último valor registrado. Será 0 de noche o si el colector no ha corrido hoy. Ejecutar `python collector.py --once` para actualizar.
- **Demanda media por hora** (combinado-001): query usa `date.hour()` + `range(-365d)`. Bug original: `hourSelection + mean()` colapsaba a un único valor.
- InfluxDB arranca con: `C:\Users\Admin\influxdb2\influxd.exe` (ventana PowerShell separada).
- Grafana arranca con: `C:\Users\Admin\grafana\bin\grafana-server.exe` (ventana PowerShell separada).
- **Script de arranque rápido:** `arrancar.bat` en el escritorio del proyecto — arranca ambos si no están corriendo.
- **Arranque automático al login:** `GemeloDigital.bat` en `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.
- **Si Grafana muestra "No Data":** verificar primero que InfluxDB está corriendo (`http://localhost:8086/health`). Este fue el problema inicial.

---

## Historial de fases completadas

| Fecha | Fase completada | Notas |
|-------|----------------|-------|
| 2026-05-26 | Fase 0 — Planificación | Roadmap definido, contexto creado |
| 2026-05-26 | Fase 1 — Completa ✅ | venv+deps, Open-Meteo, REE (ESIOS+sintético), InfluxDB v2.9.1, Grafana conectado a InfluxDB vía Flux |
| 2026-05-26 | Fase 2 — Completa ✅ | influx_writer, collector (--once / --backfill), 250+49 puntos en InfluxDB verificados |
| 2026-05-26 | Fase 3 — Completa ✅ (v2) | Backfill 365d (8784 pts clima real + energía correlacionada). Notebooks rehecho con explicaciones. 9 gráficos. |
| 2026-05-26 | Fase 4 — Completa ✅ | 3 dashboards Grafana + alerta demanda >33k MW. UIDs: energia-001, clima-001, combinado-001 |
| 2026-05-26 | Fase 5 — Completa ✅ | Prophet entrenado (365d), modelo pkl en prediction/, forecast 24h en InfluxDB, panel en Grafana |
| 2026-05-27 | Fase 6 — Completa ✅ | 04_anomaly.ipynb (Z-score + Isolation Forest), anomaly_detector.py CLI, 8751 pts + 493 anomalías en InfluxDB, panel Grafana |
