"""
Carga datos de InfluxDB en pandas DataFrames listos para análisis.
"""

import os
import sys
import warnings
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.warnings import MissingPivotFunction

warnings.simplefilter("ignore", MissingPivotFunction)

# Permite importar desde el directorio raíz del proyecto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))


def _get_client():
    return InfluxDBClient(
        url=os.getenv("INFLUX_URL", "http://localhost:8086"),
        token=os.getenv("INFLUX_TOKEN"),
        org=os.getenv("INFLUX_ORG", "gemelo_digital"),
    )


def load_weather(hours: int = 48) -> pd.DataFrame:
    """
    Carga datos meteorológicos de InfluxDB.
    Devuelve DataFrame con índice temporal y columnas:
      temperature_c, humidity_pct, wind_speed_kmh,
      cloud_cover_pct, solar_radiation_wm2
    """
    query = f"""
from(bucket: "gemelo_digital")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r._measurement == "weather")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["_time", "temperature_c", "humidity_pct",
                     "wind_speed_kmh", "cloud_cover_pct", "solar_radiation_wm2"])
  |> sort(columns: ["_time"])
"""
    with _get_client() as client:
        df = client.query_api().query_data_frame(query)

    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns={"_time": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    df = df[[c for c in ["temperature_c", "humidity_pct", "wind_speed_kmh",
                          "cloud_cover_pct", "solar_radiation_wm2"] if c in df.columns]]
    # Eliminar duplicados (pueden venir del backfill + ciclos normales)
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    return df


def load_energy(hours: int = 48) -> pd.DataFrame:
    """
    Carga datos de demanda eléctrica de InfluxDB.
    Devuelve DataFrame con índice temporal y columna: demand_mw
    """
    query = f"""
from(bucket: "gemelo_digital")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r._measurement == "energy" and r._field == "demand_mw")
  |> sort(columns: ["_time"])
"""
    with _get_client() as client:
        df = client.query_api().query_data_frame(query)

    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns={"_time": "timestamp", "_value": "demand_mw"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")[["demand_mw"]]
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    return df


def load_merged(hours: int = 48, freq: str = "1h") -> pd.DataFrame:
    """
    Carga y combina clima + energía en un solo DataFrame alineado por hora.
    Los datos se remuestrean a la frecuencia indicada (por defecto 1h).
    """
    weather = load_weather(hours).resample(freq).mean()
    energy  = load_energy(hours).resample(freq).mean()
    df = pd.concat([weather, energy], axis=1, sort=True)
    df = df.dropna()
    df.index = df.index.tz_convert("Europe/Madrid")
    df["hour"]       = df.index.hour
    df["weekday"]    = df.index.dayofweek      # 0=lunes, 6=domingo
    df["is_weekend"] = df["weekday"] >= 5
    return df


if __name__ == "__main__":
    df = load_merged()
    print(f"Dataset combinado: {len(df)} filas")
    print(df.head())
    print(df.dtypes)
