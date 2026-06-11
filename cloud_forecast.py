"""
cloud_forecast.py — Predicción Prophet 24h para entornos cloud (GitHub Actions).

Lee el histórico de datos desde Supabase (sin InfluxDB).
Carga el modelo prophet_model.pkl del repo.
Escribe las predicciones en la tabla 'forecast' de Supabase.

Dependencias: httpx supabase python-dotenv pandas numpy prophet

Uso:
    python cloud_forecast.py
    python cloud_forecast.py --hours 48   # predecir 48h en vez de 24h
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

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "prediction", "prophet_model.pkl")


# ---------------------------------------------------------------------------
# Carga del modelo
# ---------------------------------------------------------------------------

def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Modelo no encontrado en {MODEL_PATH}\n"
            "Ejecuta primero: python prediction/forecast.py --retrain"
        )
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    log.info(f"Modelo Prophet cargado desde {MODEL_PATH}")
    return model


# ---------------------------------------------------------------------------
# Pronóstico de temperatura (Open-Meteo)
# ---------------------------------------------------------------------------

def fetch_temperature_forecast(hours: int = 24) -> pd.DataFrame:
    """Descarga el pronóstico de temperatura de Open-Meteo para las próximas N horas."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 40.4168,
        "longitude": -3.7038,
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
    log.info(
        f"Temperatura prevista: {df.temperature_c.min():.1f}–"
        f"{df.temperature_c.max():.1f}°C ({len(df)} puntos)"
    )
    return df


# ---------------------------------------------------------------------------
# Generación de predicción
# ---------------------------------------------------------------------------

def predict(model, hours: int = 24) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Genera predicción para las próximas N horas. Devuelve (forecast_df, futuro_df)."""
    futuro = fetch_temperature_forecast(hours)
    log.info("Generando prediccion Prophet...")
    fc = model.predict(futuro)
    log.info(
        f"Pico: {fc['yhat'].max():.0f} MW  |  "
        f"Valle: {fc['yhat'].min():.0f} MW"
    )
    return fc, futuro


# ---------------------------------------------------------------------------
# Escritura en Supabase
# ---------------------------------------------------------------------------

def save_forecast_supabase(forecast_df: pd.DataFrame) -> None:
    """Escribe el forecast en la tabla 'forecast' de Supabase."""
    from ingestion.supabase_writer import write_forecast_batch

    records = [
        {
            "ts":              row["ds"].isoformat() + "Z",
            "demand_mw":       float(row["yhat"]),
            "demand_mw_upper": float(row["yhat_upper"]),
            "demand_mw_lower": float(row["yhat_lower"]),
            "model":           "prophet_v1",
        }
        for _, row in forecast_df.iterrows()
    ]
    write_forecast_batch(records)
    log.info(f"{len(records)} puntos escritos en Supabase (tabla: forecast)")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prediccion Prophet 24h — cloud (Supabase)")
    parser.add_argument("--hours", type=int, default=24, help="Horizonte de prediccion en horas (def: 24)")
    args = parser.parse_args()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log.info(f"=== cloud_forecast {now_str} ===")

    model = load_model()
    fc, _ = predict(model, hours=args.hours)
    save_forecast_supabase(fc)

    log.info("=== cloud_forecast completado ===")


if __name__ == "__main__":
    main()
