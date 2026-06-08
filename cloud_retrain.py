"""
cloud_retrain.py — Reentrena el modelo Prophet con los últimos 12 meses.

Lee weather + energy desde Supabase con paginación (evita el límite
max_rows=1000 de PostgREST), reentrena Prophet y guarda el .pkl.
Diseñado para correr en GitHub Actions mensualmente.

El workflow commitea el nuevo .pkl al repo tras el entrenamiento.

Dependencias: supabase python-dotenv pandas numpy prophet cmdstanpy

Uso:
    python cloud_retrain.py
    python cloud_retrain.py --months 18   # usar 18 meses de histórico
"""

import os
import sys
import pickle
import argparse
import logging
from datetime import datetime, timezone, timedelta

import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "prediction", "prophet_model.pkl")
CHUNK_SIZE = 1000   # max_rows de PostgREST — paginamos en bloques de 1000


def paginate(sb, table: str, select: str, since: str) -> list[dict]:
    """Lee todos los registros de una tabla desde 'since' con paginación."""
    all_rows = []
    offset   = 0
    while True:
        res = (
            sb.table(table)
            .select(select)
            .gte("ts", since)
            .order("ts")
            .range(offset, offset + CHUNK_SIZE - 1)
            .execute()
        )
        batch = res.data or []
        all_rows.extend(batch)
        log.info(f"  {table}: +{len(batch)} filas (total {len(all_rows)})")
        if len(batch) < CHUNK_SIZE:
            break
        offset += CHUNK_SIZE
    return all_rows


def load_training_data(sb, months: int) -> pd.DataFrame:
    """Carga y cruza weather + energy de los últimos N meses."""
    since = (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
    log.info(f"Cargando datos desde {since[:10]} ({months} meses)...")

    weather_rows = paginate(sb, "weather", "ts,temperature_c", since)
    energy_rows  = paginate(sb, "energy",  "ts,demand_mw",     since)
    log.info(f"Total: {len(weather_rows)} registros clima, {len(energy_rows)} energía")

    df_w = pd.DataFrame(weather_rows)
    df_e = pd.DataFrame(energy_rows)

    if df_w.empty or df_e.empty:
        raise ValueError("Datos insuficientes en Supabase para reentrenar")

    df_w["ts"] = pd.to_datetime(df_w["ts"], utc=True).dt.floor("h")
    df_e["ts"] = pd.to_datetime(df_e["ts"], utc=True).dt.floor("h")

    df = df_e.set_index("ts").join(df_w.set_index("ts"), how="inner")
    df = df.dropna(subset=["demand_mw", "temperature_c"])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    log.info(f"Dataset final: {len(df)} filas ({df.index.min()} → {df.index.max()})")
    return df


def train(df: pd.DataFrame) -> object:
    """Entrena el modelo Prophet con los datos cargados."""
    from prophet import Prophet

    df_train = pd.DataFrame({
        "ds":            df.index.tz_convert("UTC").tz_localize(None),
        "y":             df["demand_mw"].values,
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
    log.info("Entrenamiento completado")
    return model


def save_model(model) -> None:
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    size_mb = os.path.getsize(MODEL_PATH) / 1_048_576
    log.info(f"Modelo guardado en {MODEL_PATH} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Reentrenamiento mensual de Prophet")
    parser.add_argument("--months", type=int, default=12,
                        help="Meses de historico para entrenar (def: 12)")
    args = parser.parse_args()

    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.error("SUPABASE_URL y SUPABASE_SERVICE_KEY requeridos")
        sys.exit(1)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info(f"=== cloud_retrain {now_str} ({args.months} meses) ===")

    sb = create_client(url, key)
    df = load_training_data(sb, months=args.months)
    model = train(df)
    save_model(model)
    log.info("=== cloud_retrain completado ===")


if __name__ == "__main__":
    main()
