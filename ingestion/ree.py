"""
Conector con la API pública de Red Eléctrica de España (apidatos.ree.es).

No requiere token — datos públicos disponibles sin registro.
Endpoint principal: demanda/demanda-tiempo-real (resolución 5 min, filtramos a horario)

Si en el futuro se obtiene el token ESIOS, se puede usar fetch_demand_esios()
para acceder a más indicadores (precio, generación por tecnología, etc.)
"""

import os
import httpx
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API pública REE (sin token)
# ---------------------------------------------------------------------------

PUBLIC_BASE = "https://apidatos.ree.es/es/datos"
MADRID_TZ   = ZoneInfo("Europe/Madrid")


def _parse_ree_datetime(dt_str: str) -> datetime:
    """Parsea el formato REE '2025-05-01T00:00:00.000+02:00' a UTC aware."""
    # Python no soporta milisegundos + offset directamente, limpiamos
    clean = dt_str[:19] + dt_str[23:]   # quita los milisegundos
    return datetime.fromisoformat(clean).astimezone(timezone.utc)


def fetch_demand_real(start_date: str, end_date: str) -> list[dict]:
    """
    Descarga demanda real peninsular desde la API pública de REE.

    Args:
        start_date: 'YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM'
        end_date:   'YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM'

    Returns:
        Lista de {'timestamp': str ISO UTC, 'demand_mw': float}
        con granularidad horaria (filtra valores en punto de cada hora).
    """
    # Asegurar formato con hora
    if len(start_date) == 10: start_date += "T00:00"
    if len(end_date)   == 10: end_date   += "T23:59"

    params = {
        "start_date": start_date,
        "end_date":   end_date,
        "time_trunc": "hour",
        "geo_limit":  "peninsular",
    }
    url = f"{PUBLIC_BASE}/demanda/demanda-tiempo-real"
    resp = httpx.get(url, params=params, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()

    # Extraer serie "Real"
    real_series = next(
        (item for item in data.get("included", []) if item["type"] == "Real"),
        None,
    )
    if not real_series:
        return []

    values = real_series["attributes"]["values"]

    # La API devuelve datos cada ~5 min. Filtramos solo los puntos en punto (:00)
    records = []
    seen_hours = set()
    for v in values:
        dt_utc = _parse_ree_datetime(v["datetime"])
        # Conservar solo el primer punto de cada hora UTC (minuto == 0)
        if dt_utc.minute == 0:
            key = dt_utc.replace(second=0, microsecond=0)
            if key not in seen_hours:
                seen_hours.add(key)
                records.append({
                    "timestamp": key.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "demand_mw": float(v["value"]),
                })

    return sorted(records, key=lambda r: r["timestamp"])


def fetch_demand_real_range(
    start: datetime, end: datetime, chunk_days: int = 30
) -> list[dict]:
    """
    Descarga demanda real por bloques para cubrir rangos largos (backfill).
    Hace una petición por cada bloque de `chunk_days` días.
    """
    records = []
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        try:
            chunk = fetch_demand_real(
                cursor.strftime("%Y-%m-%dT%H:%M"),
                chunk_end.strftime("%Y-%m-%dT%H:%M"),
            )
            records.extend(chunk)
            print(f"  REE [{cursor.date()} -> {chunk_end.date()}]: {len(chunk)} registros")
        except Exception as e:
            print(f"  REE error [{cursor.date()}]: {e}")
        # Avanzar al inicio del día siguiente al chunk_end para evitar solapamientos
        cursor = (chunk_end + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return records


def fetch_demand(hours_back: int = 24) -> list[dict]:
    """
    Wrapper principal: usa la API pública REE.
    Fallback a sintético si la API falla.
    """
    now   = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours_back)
    try:
        records = fetch_demand_real(
            start.strftime("%Y-%m-%dT%H:%M"),
            now.strftime("%Y-%m-%dT%H:%M"),
        )
        if records:
            return records
    except Exception as e:
        print(f"[REE] API pública falló: {e} — usando sintético")
    return fetch_demand_synthetic(hours_back)


# ---------------------------------------------------------------------------
# API ESIOS con token (opcional — más indicadores)
# ---------------------------------------------------------------------------

ESIOS_BASE = "https://api.esios.ree.es"
ESIOS_INDICATORS = {
    "demand_mw":     1014,
    "price_eur_mwh": 600,
    "solar_mw":      10034,
    "wind_mw":       10033,
}


def _get_esios_headers() -> dict:
    token = os.getenv("ESIOS_TOKEN")
    if not token:
        raise EnvironmentError("ESIOS_TOKEN no encontrado en .env")
    return {
        "Accept": "application/json; application/vnd.esios-api-v2+json",
        "Content-Type": "application/json",
        "Authorization": f"Token token={token}",
    }


def fetch_demand_esios(hours_back: int = 24) -> list[dict]:
    """Usa el token ESIOS para obtener demanda real (si está disponible)."""
    now   = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours_back)
    params = {
        "start_date": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_date":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_trunc": "hour",
    }
    url = f"{ESIOS_BASE}/indicators/{ESIOS_INDICATORS['demand_mw']}"
    resp = httpx.get(url, headers=_get_esios_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"timestamp": v["datetime"], "demand_mw": v["value"]}
        for v in data["indicator"]["values"]
    ]


# ---------------------------------------------------------------------------
# Datos sintéticos (fallback sin conectividad)
# ---------------------------------------------------------------------------

def fetch_demand_synthetic(hours_back: int = 24) -> list[dict]:
    """Genera demanda sintética realista. Solo como fallback."""
    import math, random
    now = datetime.now(timezone.utc)
    records = []
    for i in range(hours_back, 0, -1):
        ts   = now - timedelta(hours=i)
        hour = ts.astimezone(MADRID_TZ).hour
        base = 22000
        day_curve = 8000 * math.sin(math.pi * (hour - 6) / 14) if 6 <= hour <= 22 else 0
        noise = random.gauss(0, 300)
        demand = max(18000, base + day_curve + noise)
        records.append({
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "demand_mw": round(demand, 1),
        })
    return records


def generate_demand_from_weather_records(weather_records: list[dict]) -> list[dict]:
    """
    Genera demanda sintética correlacionada con temperatura real.
    Solo para backfill cuando no hay datos reales disponibles.
    """
    import math, random
    random.seed(42)

    def temp_effect(t: float) -> float:
        if t < 18:  return (18 - t) ** 1.6 * 130
        elif t > 22: return (t - 22) ** 1.8 * 90
        return 0.0

    HOUR_FACTOR = {
        0: 0.72, 1: 0.69, 2: 0.67, 3: 0.66, 4: 0.66, 5: 0.68,
        6: 0.73, 7: 0.82, 8: 0.93, 9: 1.02, 10: 1.08, 11: 1.10,
        12: 1.07, 13: 1.02, 14: 0.97, 15: 0.94, 16: 0.95, 17: 0.98,
        18: 1.03, 19: 1.09, 20: 1.12, 21: 1.08, 22: 0.98, 23: 0.85,
    }

    results = []
    for rec in weather_records:
        ts_str = rec["timestamp"]
        temp   = rec.get("temperature_c", 18.0)
        ts_local_str = rec.get("timestamp_local", ts_str)
        ts_local_clean = ts_local_str.replace("Z", "+00:00")
        if "+" not in ts_local_clean and len(ts_local_clean) <= 16:
            ts_local_clean += "+00:00"
        try:
            ts_local = datetime.fromisoformat(ts_local_clean)
            if ts_local.tzinfo is not None and ts_local.utcoffset().total_seconds() == 0:
                ts_local = ts_local.astimezone(MADRID_TZ)
        except Exception:
            ts_local = datetime.now(timezone.utc)

        hour    = ts_local.hour
        weekday = ts_local.weekday()
        base       = 24_000
        t_effect   = temp_effect(temp)
        h_factor   = HOUR_FACTOR.get(hour, 1.0)
        wd_factor  = 0.88 if weekday >= 5 else 1.0
        noise      = random.gauss(0, 400)
        demand     = max(16_000, (base + t_effect) * h_factor * wd_factor + noise)
        results.append({"timestamp": ts_str, "demand_mw": round(demand, 1)})
    return results


if __name__ == "__main__":
    print("=== REE API Pública — Demanda real (últimas 3h) ===")
    records = fetch_demand(hours_back=3)
    for r in records:
        print(f"  {r['timestamp']}  {r['demand_mw']:.0f} MW")
    print(f"\nTotal: {len(records)} registros")
