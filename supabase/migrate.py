"""
supabase/migrate.py — Migra todos los datos de InfluxDB local a Supabase.

Uso:
    python supabase/migrate.py

Requiere en .env:
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY=eyJ...
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET (datos locales)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from influxdb_client import InfluxDBClient
from ingestion.supabase_writer import (
    write_weather_batch, write_energy_batch,
    write_forecast_batch, write_anomalies_batch,
)

INFLUX_URL    = os.getenv("INFLUX_URL",    "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN")
INFLUX_ORG    = os.getenv("INFLUX_ORG",   "gemelo_digital")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET","gemelo_digital")


def query_influx(flux: str) -> list[dict]:
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    result = []
    for table in client.query_api().query(flux):
        for record in table.records:
            result.append(dict(record.values))
    client.close()
    return result


def migrate_weather():
    print("Migrando weather...")
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -11y)
      |> filter(fn: (r) => r._measurement == "weather")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
    '''
    rows = query_influx(flux)
    records = [{
        "timestamp":            str(r["_time"]),
        "temperature_c":        r.get("temperature_c"),
        "humidity_pct":         r.get("humidity_pct"),
        "wind_speed_kmh":       r.get("wind_speed_kmh"),
        "cloud_cover_pct":      r.get("cloud_cover_pct"),
        "solar_radiation_wm2":  r.get("solar_radiation_wm2"),
    } for r in rows]
    write_weather_batch(records)
    print(f"  {len(records)} filas migradas")


def migrate_energy():
    print("Migrando energy...")
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -11y)
      |> filter(fn: (r) => r._measurement == "energy" and r._field == "demand_mw")
      |> sort(columns: ["_time"])
    '''
    rows = query_influx(flux)
    records = [{
        "timestamp": str(r["_time"]),
        "demand_mw": r["_value"],
        "source":    r.get("source", "ree_real"),
    } for r in rows]
    write_energy_batch(records)
    print(f"  {len(records)} filas migradas")


def migrate_forecast():
    print("Migrando forecast...")
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r._measurement == "forecast")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
    '''
    rows = query_influx(flux)
    records = [{
        "ts":              str(r["_time"]),
        "demand_mw":       r.get("demand_mw"),
        "demand_mw_upper": r.get("demand_mw_upper"),
        "demand_mw_lower": r.get("demand_mw_lower"),
    } for r in rows]
    if records:
        write_forecast_batch(records)
    print(f"  {len(records)} filas migradas")


def migrate_anomalies():
    print("Migrando anomalies...")
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -11y)
      |> filter(fn: (r) => r._measurement == "anomalies")
      |> pivot(rowKey: ["_time", "nivel"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
    '''
    rows = query_influx(flux)
    records = [{
        "ts":            str(r["_time"]),
        "residual_mw":   r.get("residual_mw"),
        "z_score":       r.get("z_score"),
        "iforest_score": r.get("iforest_score"),
        "is_anomaly":    int(r.get("is_anomaly", 0)),
        "nivel":         r.get("nivel", "normal"),
    } for r in rows]
    write_anomalies_batch(records)
    print(f"  {len(records)} filas migradas")


if __name__ == "__main__":
    print("=== Migracion InfluxDB -> Supabase ===\n")
    migrate_weather()
    migrate_energy()
    migrate_forecast()
    migrate_anomalies()
    print("\nMigracion completada.")
