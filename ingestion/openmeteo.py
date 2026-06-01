import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Coordenadas del centro de la Península Ibérica (Madrid)
LATITUDE = 40.4168
LONGITUDE = -3.7038

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "cloud_cover",
    "shortwave_radiation",  # radiación solar
]

MADRID_TZ = ZoneInfo("Europe/Madrid")


def _madrid_str_to_utc(time_str: str) -> str:
    """
    Convierte un string de hora local Madrid ('2026-05-28T13:00') a UTC ISO.
    Open-Meteo devuelve tiempos en la timezone solicitada sin info de offset,
    por lo que hay que añadir el huso horario manualmente antes de convertir.
    """
    dt_madrid = datetime.fromisoformat(time_str).replace(tzinfo=MADRID_TZ)
    return dt_madrid.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_current_weather() -> dict:
    """Devuelve las condiciones meteorológicas actuales para Madrid."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(HOURLY_VARS),
        "forecast_days": 1,
        "timezone": "Europe/Madrid",
    }
    response = httpx.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Encontrar el índice de la hora actual en hora local Madrid
    now_madrid = datetime.now(timezone.utc).astimezone(MADRID_TZ)
    now_str = now_madrid.strftime("%Y-%m-%dT%H:00")
    times = data["hourly"]["time"]
    idx = next((i for i, t in enumerate(times) if t == now_str), -1)
    if idx == -1:
        idx = 0  # fallback a primera hora disponible

    return {
        "timestamp": _madrid_str_to_utc(times[idx]),   # UTC correcto
        "temperature_c": data["hourly"]["temperature_2m"][idx],
        "humidity_pct": data["hourly"]["relative_humidity_2m"][idx],
        "wind_speed_kmh": data["hourly"]["wind_speed_10m"][idx],
        "cloud_cover_pct": data["hourly"]["cloud_cover"][idx],
        "solar_radiation_wm2": data["hourly"]["shortwave_radiation"][idx],
    }


def fetch_historical_weather(start_date: str, end_date: str) -> list[dict]:
    """Devuelve datos horarios históricos entre start_date y end_date (YYYY-MM-DD)."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Europe/Madrid",
    }
    response = httpx.get(url, params=params, timeout=180)   # 3 min para rangos de 10 años
    response.raise_for_status()
    data = response.json()

    records = []
    times = data["hourly"]["time"]
    for i, t in enumerate(times):
        records.append({
            "timestamp": _madrid_str_to_utc(t),         # UTC correcto
            "timestamp_local": t,                        # hora local (para el modelo de demanda)
            "temperature_c": data["hourly"]["temperature_2m"][i],
            "humidity_pct": data["hourly"]["relative_humidity_2m"][i],
            "wind_speed_kmh": data["hourly"]["wind_speed_10m"][i],
            "cloud_cover_pct": data["hourly"]["cloud_cover"][i],
            "solar_radiation_wm2": data["hourly"]["shortwave_radiation"][i],
        })
    return records


if __name__ == "__main__":
    print("=== Open-Meteo — datos actuales ===")
    weather = fetch_current_weather()
    for k, v in weather.items():
        print(f"  {k}: {v}")
