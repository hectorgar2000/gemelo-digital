"""
ingestion/supabase_writer.py — Escritura de datos en Supabase (PostgreSQL).

Reemplaza influx_writer.py para el despliegue en producción.
Usa upsert para que re-ejecuciones del colector no dupliquen datos.
"""

import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def _get_client():
    """Devuelve cliente Supabase autenticado con la service_role key."""
    from supabase import create_client
    url   = os.getenv("SUPABASE_URL")
    key   = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL y SUPABASE_SERVICE_KEY requeridos en .env")
    return create_client(url, key)


def _fmt_ts(ts) -> str:
    """Convierte timestamp a string ISO UTC para PostgreSQL."""
    if isinstance(ts, str):
        # Normalizar formato
        ts = ts.replace("Z", "+00:00")
        if "+" not in ts:
            ts += "+00:00"
        ts = datetime.fromisoformat(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def write_weather(record: dict) -> None:
    client = _get_client()
    client.table("weather").upsert({
        "ts":                   _fmt_ts(record["timestamp"]),
        "temperature_c":        record.get("temperature_c"),
        "humidity_pct":         record.get("humidity_pct"),
        "wind_speed_kmh":       record.get("wind_speed_kmh"),
        "cloud_cover_pct":      record.get("cloud_cover_pct"),
        "solar_radiation_wm2":  record.get("solar_radiation_wm2"),
    }, on_conflict="ts").execute()


def write_weather_batch(records: list[dict], chunk_size: int = 500) -> None:
    client = _get_client()
    rows = [{
        "ts":                  _fmt_ts(r["timestamp"]),
        "temperature_c":       r.get("temperature_c"),
        "humidity_pct":        r.get("humidity_pct"),
        "wind_speed_kmh":      r.get("wind_speed_kmh"),
        "cloud_cover_pct":     r.get("cloud_cover_pct"),
        "solar_radiation_wm2": r.get("solar_radiation_wm2"),
    } for r in records]
    for i in range(0, len(rows), chunk_size):
        client.table("weather").upsert(rows[i:i+chunk_size], on_conflict="ts").execute()


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------

def write_energy(record: dict, source: str = "ree_real") -> None:
    client = _get_client()
    client.table("energy").upsert({
        "ts":        _fmt_ts(record["timestamp"]),
        "demand_mw": record["demand_mw"],
        "source":    source,
    }, on_conflict="ts").execute()


def write_energy_batch(records: list[dict], source: str = "ree_real", chunk_size: int = 500) -> None:
    client = _get_client()
    rows = [{
        "ts":        _fmt_ts(r["timestamp"]),
        "demand_mw": r["demand_mw"],
        "source":    source,
    } for r in records]
    for i in range(0, len(rows), chunk_size):
        client.table("energy").upsert(rows[i:i+chunk_size], on_conflict="ts").execute()


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

def write_forecast_batch(records: list[dict], chunk_size: int = 500) -> None:
    client = _get_client()
    rows = [{
        "ts":              _fmt_ts(r["ts"]),
        "demand_mw":       r.get("demand_mw"),
        "demand_mw_upper": r.get("demand_mw_upper"),
        "demand_mw_lower": r.get("demand_mw_lower"),
        "model":           r.get("model", "prophet_v1"),
    } for r in records]
    for i in range(0, len(rows), chunk_size):
        client.table("forecast").upsert(rows[i:i+chunk_size], on_conflict="ts").execute()


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

def write_anomalies_batch(records: list[dict], chunk_size: int = 500) -> None:
    client = _get_client()
    rows = [{
        "ts":            _fmt_ts(r["ts"]),
        "residual_mw":   r.get("residual_mw"),
        "z_score":       r.get("z_score"),
        "iforest_score": r.get("iforest_score"),
        "is_anomaly":    int(r.get("is_anomaly", 0)),
        "nivel":         r.get("nivel", "normal"),
    } for r in records]
    for i in range(0, len(rows), chunk_size):
        client.table("anomalies").upsert(rows[i:i+chunk_size], on_conflict="ts").execute()
