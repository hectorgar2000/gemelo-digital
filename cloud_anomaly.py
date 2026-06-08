"""
cloud_anomaly.py — Detección de anomalías para entornos cloud (GitHub Actions).

Lee clima + energía de las últimas N horas desde Supabase (sin InfluxDB).
Usa el modelo prophet_model.pkl del repo para calcular residuos.
Detecta anomalías con Z-score + Isolation Forest.
Escribe resultados en la tabla 'anomalies' de Supabase.

Dependencias: httpx supabase python-dotenv pandas numpy prophet scikit-learn

Uso:
    python cloud_anomaly.py
    python cloud_anomaly.py --hours 336   # analizar las últimas 2 semanas
"""

import os
import sys
import pickle
import logging
import argparse
import warnings
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "prediction", "prophet_model.pkl")
Z_THRESHOLD   = 2.5
CONTAMINATION = 0.02


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
# Carga de datos desde Supabase
# ---------------------------------------------------------------------------

def load_data_from_supabase(hours: int = 168) -> pd.DataFrame:
    """
    Carga las últimas N horas de clima + energía desde Supabase.
    Devuelve un DataFrame con columnas: demand_mw, temperature_c, humidity_pct,
    wind_speed_kmh, solar_radiation_wm2, hour, is_weekend.
    """
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL y SUPABASE_SERVICE_KEY requeridos")

    sb = create_client(url, key)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # Cargar clima
    res_w = (
        sb.from_("weather")
        .select("ts,temperature_c,humidity_pct,wind_speed_kmh,solar_radiation_wm2")
        .gte("ts", since)
        .order("ts")
        .execute()
    )
    # Cargar energía
    res_e = (
        sb.from_("energy")
        .select("ts,demand_mw")
        .gte("ts", since)
        .order("ts")
        .execute()
    )

    if not res_w.data or not res_e.data:
        raise ValueError(f"Datos insuficientes en Supabase (weather: {len(res_w.data or [])}, energy: {len(res_e.data or [])})")

    df_w = pd.DataFrame(res_w.data)
    df_w["ts"] = pd.to_datetime(df_w["ts"], utc=True)
    df_w = df_w.set_index("ts").sort_index()

    df_e = pd.DataFrame(res_e.data)
    df_e["ts"] = pd.to_datetime(df_e["ts"], utc=True)
    df_e = df_e.set_index("ts").sort_index()

    # Join por hora truncada
    df_w.index = df_w.index.floor("h")
    df_e.index = df_e.index.floor("h")
    df = df_e.join(df_w, how="inner")
    df = df.dropna(subset=["demand_mw", "temperature_c"])

    # Features para Isolation Forest — convertir a hora local Madrid
    # (el índice es UTC; df.index.hour daría horas UTC, no las horas locales
    #  que definen los patrones de demanda: 22:00 UTC = 00:00 Madrid en verano)
    idx_madrid       = df.index.tz_convert(MADRID_TZ)
    df["hour"]       = idx_madrid.hour
    df["is_weekend"] = idx_madrid.dayofweek.isin([5, 6]).astype(int)

    log.info(
        f"Datos cargados desde Supabase: {len(df)} registros "
        f"({df.index.min()} → {df.index.max()})"
    )
    return df


# ---------------------------------------------------------------------------
# Detección de anomalías
# ---------------------------------------------------------------------------

def compute_prophet_residuals(model, df: pd.DataFrame) -> pd.DataFrame:
    df_prophet = pd.DataFrame({
        "ds":            df.index.tz_convert("UTC").tz_localize(None),
        "temperature_c": df["temperature_c"].values,
    })
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pred = model.predict(df_prophet)

    df = df.copy()
    df["yhat"]        = pred["yhat"].values
    df["residual_mw"] = df["demand_mw"] - df["yhat"]
    return df


def detect_zscore(df: pd.DataFrame) -> pd.DataFrame:
    mean_r = df["residual_mw"].mean()
    std_r  = df["residual_mw"].std()
    df = df.copy()
    df["z_score"]        = (df["residual_mw"] - mean_r) / std_r
    df["anomaly_zscore"] = df["z_score"].abs() > Z_THRESHOLD
    n = df["anomaly_zscore"].sum()
    log.info(f"Z-score: {n} anomalías ({n / len(df) * 100:.1f}%) con |Z|>{Z_THRESHOLD}")
    return df


def detect_isolation_forest(df: pd.DataFrame) -> pd.DataFrame:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    features = ["demand_mw", "temperature_c", "hour", "is_weekend"]
    optional = ["humidity_pct", "wind_speed_kmh", "solar_radiation_wm2"]
    for col in optional:
        if col in df.columns:
            features.append(col)

    X = df[features].copy().fillna(df[features].median())
    X_scaled = StandardScaler().fit_transform(X)

    model_if = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=42,
        n_jobs=-1,
    )
    model_if.fit(X_scaled)

    df = df.copy()
    df["iforest_score"]   = -model_if.score_samples(X_scaled)
    df["anomaly_iforest"] = model_if.predict(X_scaled) == -1

    n = df["anomaly_iforest"].sum()
    log.info(f"Isolation Forest: {n} anomalías ({n / len(df) * 100:.1f}%)")
    return df


def classify_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_anomaly"] = df["anomaly_zscore"] | df["anomaly_iforest"]

    def nivel(row):
        if row["anomaly_zscore"] and row["anomaly_iforest"]:
            return "alta"
        elif row["anomaly_zscore"] or row["anomaly_iforest"]:
            return "media"
        return "normal"

    df["nivel"] = df.apply(nivel, axis=1)
    alta  = (df["nivel"] == "alta").sum()
    media = (df["nivel"] == "media").sum()
    log.info(f"Clasificación: {alta} alta confianza | {media} media confianza")
    return df


# ---------------------------------------------------------------------------
# Escritura en Supabase
# ---------------------------------------------------------------------------

def save_anomalies_supabase(df: pd.DataFrame) -> None:
    """Escribe todos los puntos en la tabla 'anomalies' de Supabase."""
    from ingestion.supabase_writer import write_anomalies_batch

    records = []
    for ts, row in df.iterrows():
        ts_str = ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        records.append({
            "ts":            ts_str,
            "residual_mw":   float(row.get("residual_mw", 0)),
            "z_score":       float(row.get("z_score", 0)),
            "iforest_score": float(row.get("iforest_score", 0)),
            "is_anomaly":    int(row.get("is_anomaly", 0)),
            "nivel":         row.get("nivel", "normal"),
        })

    write_anomalies_batch(records)
    anomalias = sum(1 for r in records if r["is_anomaly"])
    log.info(f"{len(records)} puntos escritos en Supabase ({anomalias} anomalías marcadas)")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Detección de anomalías — cloud (Supabase)")
    parser.add_argument("--hours", type=int, default=168, help="Horas a analizar (def: 168 = 7d)")
    args = parser.parse_args()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log.info(f"=== cloud_anomaly {now_str} ===")

    model = load_model()
    df    = load_data_from_supabase(hours=args.hours)
    df    = compute_prophet_residuals(model, df)
    df    = detect_zscore(df)
    df    = detect_isolation_forest(df)
    df    = classify_anomalies(df)
    save_anomalies_supabase(df)

    log.info("=== cloud_anomaly completado ===")


if __name__ == "__main__":
    main()
