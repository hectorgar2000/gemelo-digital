"""
prediction/forecast.py — Predicción de demanda eléctrica para las próximas 24h.

Uso:
    python prediction/forecast.py              # predice y guarda en InfluxDB
    python prediction/forecast.py --retrain    # reentrena el modelo antes de predecir
    python prediction/forecast.py --plot       # muestra gráfico de la predicción

El modelo se guarda en prediction/prophet_model.pkl y se reutiliza en
ejecuciones posteriores sin necesidad de reentrenar.
"""

import os
import sys
import pickle
import logging
import argparse
from datetime import datetime, timezone, timedelta

import httpx
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from analysis.data_loader import load_merged
from ingestion.influx_writer import _get_client

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "prophet_model.pkl")


# ---------------------------------------------------------------------------
# Entrenamiento
# ---------------------------------------------------------------------------

def train(days: int = 3650) -> object:
    """Entrena Prophet con los últimos N días de datos y guarda el modelo."""
    from prophet import Prophet

    log.info(f"Cargando {days} dias de datos para entrenamiento...")
    df = load_merged(hours=days * 24)
    df = df.dropna(subset=["demand_mw", "temperature_c"]).sort_index()

    df_train = pd.DataFrame({
        "ds": df.index.tz_convert("UTC").tz_localize(None),
        "y":  df["demand_mw"].values,
        "temperature_c": df["temperature_c"].values,
    })

    log.info(f"Entrenando Prophet con {len(df_train)} filas...")
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=True,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
        interval_width=0.95,
    )
    model.add_regressor("temperature_c", standardize=True)
    model.fit(df_train)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    log.info(f"Modelo guardado en {MODEL_PATH}")
    return model


def load_model() -> object:
    """Carga el modelo serializado. Entrena si no existe."""
    if not os.path.exists(MODEL_PATH):
        log.info("No se encontró modelo guardado — entrenando por primera vez...")
        return train()
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    log.info(f"Modelo cargado desde {MODEL_PATH}")
    return model


# ---------------------------------------------------------------------------
# Pronóstico meteorológico
# ---------------------------------------------------------------------------

def fetch_temperature_forecast(hours: int = 24) -> pd.DataFrame:
    """Descarga el pronóstico de temperatura de Open-Meteo para las próximas N horas."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 40.4168, "longitude": -3.7038,
        "hourly": "temperature_2m",
        "forecast_days": max(2, hours // 24 + 1),
        "timezone": "Europe/Madrid",
    }
    resp = httpx.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame({
        "ds": pd.to_datetime(data["hourly"]["time"])
                .tz_localize("Europe/Madrid")
                .tz_convert("UTC")
                .tz_localize(None),
        "temperature_c": data["hourly"]["temperature_2m"],
    })

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    df = df[df["ds"] >= now_naive].head(hours).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Predicción y escritura en InfluxDB
# ---------------------------------------------------------------------------

def predict(model, hours: int = 24) -> pd.DataFrame:
    """Genera predicción para las próximas N horas."""
    log.info(f"Descargando pronostico meteorologico ({hours}h)...")
    futuro = fetch_temperature_forecast(hours)
    log.info(f"  Temperatura prevista: {futuro.temperature_c.min():.1f}–{futuro.temperature_c.max():.1f}°C")

    log.info("Generando prediccion...")
    fc = model.predict(futuro)
    log.info(f"  Pico: {fc['yhat'].max():.0f} MW  |  Valle: {fc['yhat'].min():.0f} MW")
    return fc, futuro


def save_forecast(forecast_df: pd.DataFrame) -> None:
    """Escribe el forecast en InfluxDB como measurement 'forecast'."""
    points = [
        Point("forecast")
        .tag("model", "prophet_v1")
        .tag("region", "peninsular")
        .field("demand_mw",       float(row["yhat"]))
        .field("demand_mw_lower", float(row["yhat_lower"]))
        .field("demand_mw_upper", float(row["yhat_upper"]))
        .time(row["ds"].to_pydatetime(), WritePrecision.S)
        for _, row in forecast_df.iterrows()
    ]
    bucket = os.getenv("INFLUX_BUCKET", "gemelo_digital")
    with _get_client() as client:
        client.write_api(write_options=SYNCHRONOUS).write(bucket=bucket, record=points)
    log.info(f"{len(points)} puntos escritos en InfluxDB (measurement: forecast)")


def plot_forecast(forecast_df: pd.DataFrame, weather_df: pd.DataFrame) -> None:
    """Muestra un gráfico rápido de la predicción."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax1 = plt.subplots(figsize=(13, 5))
    ax2 = ax1.twinx()

    ax1.fill_between(forecast_df["ds"],
                     forecast_df["yhat_lower"], forecast_df["yhat_upper"],
                     alpha=0.2, color="purple", label="IC 95%")
    ax1.plot(forecast_df["ds"], forecast_df["yhat"],
             color="purple", linewidth=2, marker="o", markersize=4, label="Demanda predicha (MW)")
    ax1.set_ylabel("Demanda predicha (MW)", color="purple")
    ax1.tick_params(axis="y", labelcolor="purple")

    ax2.plot(weather_df["ds"], weather_df["temperature_c"],
             color="red", linewidth=1.5, linestyle="--", marker="s", markersize=4,
             label="Temperatura prevista (°C)")
    ax2.set_ylabel("Temperatura (°C)", color="red")
    ax2.tick_params(axis="y", labelcolor="red")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)

    generado = datetime.now().strftime("%Y-%m-%d %H:%M")
    ax1.set_title(f"Prediccion de demanda electrica — proximas 24h  (generado: {generado})", fontsize=11)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Hh\n%d/%m"))
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prediccion de demanda electrica 24h")
    parser.add_argument("--retrain",    action="store_true", help="Reentrenar el modelo antes de predecir")
    parser.add_argument("--plot",       action="store_true", help="Mostrar grafico de la prediccion")
    parser.add_argument("--hours",      type=int, default=24,   help="Horizonte de prediccion en horas (def: 24)")
    parser.add_argument("--train-days", type=int, default=3650, dest="train_days",
                        help="Dias de historico para entrenar (def: 3650 = 10 anos)")
    args = parser.parse_args()

    train_days = getattr(args, "train_days", 3650)
    model = train(days=train_days) if args.retrain else load_model()
    fc, weather = predict(model, hours=args.hours)
    save_forecast(fc)

    if args.plot:
        plot_forecast(fc, weather)

    log.info("Prediccion completada.")


if __name__ == "__main__":
    main()
