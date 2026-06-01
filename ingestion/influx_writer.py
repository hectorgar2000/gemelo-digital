"""
Escritor de datos en InfluxDB.

Schema de measurements:
  weather  → campos: temperature_c, humidity_pct, wind_speed_kmh,
                      cloud_cover_pct, solar_radiation_wm2
             tags:    location=madrid

  energy   → campos: demand_mw
             tags:    source=synthetic | esios, region=peninsular
"""

import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()


def _get_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=os.getenv("INFLUX_URL", "http://localhost:8086"),
        token=os.getenv("INFLUX_TOKEN"),
        org=os.getenv("INFLUX_ORG", "gemelo_digital"),
    )


def write_weather(record: dict) -> None:
    """
    Escribe un registro meteorológico en InfluxDB.

    record = {
        'timestamp': '2026-05-26T11:00',   # o datetime
        'temperature_c': 22.8,
        'humidity_pct': 30,
        'wind_speed_kmh': 6.5,
        'cloud_cover_pct': 64,
        'solar_radiation_wm2': 617.0,
    }
    """
    point = (
        Point("weather")
        .tag("location", "madrid")
        .field("temperature_c",       float(record["temperature_c"]))
        .field("humidity_pct",        float(record["humidity_pct"]))
        .field("wind_speed_kmh",      float(record["wind_speed_kmh"]))
        .field("cloud_cover_pct",     float(record["cloud_cover_pct"]))
        .field("solar_radiation_wm2", float(record["solar_radiation_wm2"]))
        .time(_parse_ts(record["timestamp"]), WritePrecision.S)
    )

    with _get_client() as client:
        client.write_api(write_options=SYNCHRONOUS).write(
            bucket=os.getenv("INFLUX_BUCKET", "gemelo_digital"),
            record=point,
        )


def write_energy(record: dict, source: str = "synthetic") -> None:
    """
    Escribe un registro de demanda eléctrica en InfluxDB.

    record = {
        'timestamp': '2026-05-26T11:00:00Z',
        'demand_mw': 25871.0,
    }
    """
    point = (
        Point("energy")
        .tag("source", source)
        .tag("region", "peninsular")
        .field("demand_mw", float(record["demand_mw"]))
        .time(_parse_ts(record["timestamp"]), WritePrecision.S)
    )

    with _get_client() as client:
        client.write_api(write_options=SYNCHRONOUS).write(
            bucket=os.getenv("INFLUX_BUCKET", "gemelo_digital"),
            record=point,
        )


def write_weather_batch(records: list[dict], chunk_size: int = 2000) -> None:
    """Escribe una lista de registros meteorológicos en chunks para evitar timeouts."""
    points = [
        Point("weather")
        .tag("location", "madrid")
        .field("temperature_c",       float(r["temperature_c"]))
        .field("humidity_pct",        float(r["humidity_pct"]))
        .field("wind_speed_kmh",      float(r["wind_speed_kmh"]))
        .field("cloud_cover_pct",     float(r["cloud_cover_pct"]))
        .field("solar_radiation_wm2", float(r["solar_radiation_wm2"]))
        .time(_parse_ts(r["timestamp"]), WritePrecision.S)
        for r in records
    ]
    bucket = os.getenv("INFLUX_BUCKET", "gemelo_digital")
    with _get_client() as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        for i in range(0, len(points), chunk_size):
            write_api.write(bucket=bucket, record=points[i:i + chunk_size])


def write_energy_batch(records: list[dict], source: str = "synthetic", chunk_size: int = 2000) -> None:
    """Escribe una lista de registros de energía en chunks para evitar timeouts."""
    points = [
        Point("energy")
        .tag("source", source)
        .tag("region", "peninsular")
        .field("demand_mw", float(r["demand_mw"]))
        .time(_parse_ts(r["timestamp"]), WritePrecision.S)
        for r in records
    ]
    bucket = os.getenv("INFLUX_BUCKET", "gemelo_digital")
    with _get_client() as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        for i in range(0, len(points), chunk_size):
            write_api.write(bucket=bucket, record=points[i:i + chunk_size])


def _parse_ts(ts) -> datetime:
    """Convierte string ISO 8601 o datetime a datetime con timezone UTC."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    # Normalizar formatos: '2026-05-26T11:00', '2026-05-26T11:00:00Z', etc.
    ts = str(ts).replace(" ", "T")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    elif "+" not in ts and len(ts) <= 16:
        ts += ":00+00:00"
    elif "+" not in ts:
        ts += "+00:00"
    return datetime.fromisoformat(ts)


if __name__ == "__main__":
    # Test rápido: escribir un punto de cada measurement
    from datetime import timezone

    test_weather = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": 23.5,
        "humidity_pct": 28.0,
        "wind_speed_kmh": 7.2,
        "cloud_cover_pct": 45.0,
        "solar_radiation_wm2": 580.0,
    }
    test_energy = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "demand_mw": 27500.0,
    }

    write_weather(test_weather)
    print("weather  -> escrito OK")

    write_energy(test_energy)
    print("energy   -> escrito OK")
