"""
prediction/anomaly_detector.py — Detección de anomalías en tiempo real.

Detecta puntos donde la demanda eléctrica es inesperadamente alta o baja
dado el contexto climático, usando dos métodos complementarios:
  1. Z-score sobre los residuos del modelo Prophet (|Z| > 2.5)
  2. Isolation Forest multivariante (contamination=2%)

Uso:
    python prediction/anomaly_detector.py              # detecta y guarda en InfluxDB
    python prediction/anomaly_detector.py --hours 48   # analiza las últimas 48h
    python prediction/anomaly_detector.py --plot       # muestra gráfico de anomalías
    python prediction/anomaly_detector.py --report     # imprime tabla resumen

Salida en InfluxDB:
    Measurement: anomalies
    Campos:      residual_mw, z_score, iforest_score, is_anomaly
    Tags:        nivel (alta/media/normal), region=peninsular
"""

import os
import sys
import pickle
import logging
import argparse
import warnings

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

from analysis.data_loader import load_merged
from ingestion.influx_writer import _get_client

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

warnings.filterwarnings("ignore", message="The behavior of DataFrame concatenation")

MODEL_PATH = os.path.join(os.path.dirname(__file__), "prophet_model.pkl")

# Umbrales
Z_THRESHOLD   = 2.5    # |Z-score| para considerar anomalía por residuos
CONTAMINATION = 0.02   # Fracción esperada de anomalías para Isolation Forest


# ---------------------------------------------------------------------------
# Carga de datos y modelo
# ---------------------------------------------------------------------------

def load_model():
    """Carga el modelo Prophet serializado."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Modelo no encontrado en {MODEL_PATH}\n"
            "Ejecuta primero: python prediction/forecast.py --retrain"
        )
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    log.info(f"Modelo Prophet cargado desde {MODEL_PATH}")
    return model


def load_data(hours: int = 168) -> pd.DataFrame:
    """Carga las últimas N horas de datos combinados clima+energía."""
    log.info(f"Cargando {hours}h de datos ({hours//24}d)...")
    df = load_merged(hours=hours)
    df = df.dropna(subset=["demand_mw", "temperature_c"])
    log.info(f"  {len(df)} registros cargados ({df.index.min()} → {df.index.max()})")
    return df


# ---------------------------------------------------------------------------
# Método 1: Z-score sobre residuos Prophet
# ---------------------------------------------------------------------------

def compute_prophet_residuals(model, df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera predicciones in-sample de Prophet y calcula residuos.
    Residuo = demanda_real - demanda_predicha
    """
    log.info("Calculando predicciones in-sample con Prophet...")

    df_prophet = pd.DataFrame({
        "ds": df.index.tz_convert("UTC").tz_localize(None),
        "temperature_c": df["temperature_c"].values,
    })

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pred = model.predict(df_prophet)

    df_out = df.copy()
    df_out["yhat"]       = pred["yhat"].values
    df_out["residual_mw"] = df_out["demand_mw"] - df_out["yhat"]

    return df_out


def detect_zscore(df: pd.DataFrame, threshold: float = Z_THRESHOLD) -> pd.DataFrame:
    """
    Detección por Z-score sobre los residuos Prophet.
    Añade columnas: z_score, anomaly_zscore
    """
    mean_r = df["residual_mw"].mean()
    std_r  = df["residual_mw"].std()
    df = df.copy()
    df["z_score"]       = (df["residual_mw"] - mean_r) / std_r
    df["anomaly_zscore"] = df["z_score"].abs() > threshold
    n = df["anomaly_zscore"].sum()
    log.info(f"Z-score: {n} anomalías ({n/len(df)*100:.1f}%) con umbral |Z|>{threshold}")
    return df


# ---------------------------------------------------------------------------
# Método 2: Isolation Forest
# ---------------------------------------------------------------------------

def detect_isolation_forest(df: pd.DataFrame, contamination: float = CONTAMINATION) -> pd.DataFrame:
    """
    Detección multivariante con Isolation Forest.
    Usa: demand_mw, temperature_c, humidity_pct, wind_speed_kmh,
         solar_radiation_wm2, hour, is_weekend
    Añade columnas: iforest_score, anomaly_iforest
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    features = ["demand_mw", "temperature_c", "hour", "is_weekend"]
    optional = ["humidity_pct", "wind_speed_kmh", "solar_radiation_wm2"]
    for col in optional:
        if col in df.columns:
            features.append(col)

    X = df[features].copy()
    # Rellenar posibles NaN en columnas opcionales con la mediana
    X = X.fillna(X.median())

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    log.info(f"Isolation Forest con {len(features)} features, contamination={contamination}...")
    model_if = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    model_if.fit(X_scaled)

    df = df.copy()
    df["iforest_score"]   = -model_if.score_samples(X_scaled)   # más alto = más anómalo
    df["anomaly_iforest"] = model_if.predict(X_scaled) == -1    # -1 = anomalía

    n = df["anomaly_iforest"].sum()
    log.info(f"Isolation Forest: {n} anomalías ({n/len(df)*100:.1f}%)")
    return df


# ---------------------------------------------------------------------------
# Combinación y clasificación por nivel de confianza
# ---------------------------------------------------------------------------

def classify_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combina ambos métodos y asigna nivel de confianza:
      - alta:   ambos métodos coinciden
      - media:  solo un método detecta anomalía
      - normal: ningún método detecta anomalía
    """
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
    log.info(f"Clasificacion: {alta} anomalias alta confianza | {media} media confianza")
    return df


# ---------------------------------------------------------------------------
# Escritura en InfluxDB
# ---------------------------------------------------------------------------

def save_anomalies(df: pd.DataFrame) -> None:
    """
    Escribe los resultados en InfluxDB (measurement: anomalies).
    Se escriben TODOS los puntos (is_anomaly=0/1) para permitir
    visualización comparativa en Grafana.
    """
    points = []
    for ts, row in df.iterrows():
        # Convertir a UTC naive si tiene zona horaria
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts_utc = ts.tz_convert("UTC").tz_localize(None)
        else:
            ts_utc = ts

        p = (
            Point("anomalies")
            .tag("nivel", row["nivel"])
            .tag("region", "peninsular")
            .field("residual_mw",  float(row.get("residual_mw", 0)))
            .field("z_score",      float(row.get("z_score", 0)))
            .field("iforest_score", float(row.get("iforest_score", 0)))
            .field("is_anomaly",   int(row.get("is_anomaly", 0)))
            .time(ts_utc.to_pydatetime(), WritePrecision.S)
        )
        points.append(p)

    bucket = os.getenv("INFLUX_BUCKET", "gemelo_digital")
    with _get_client() as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        for i in range(0, len(points), 500):
            write_api.write(bucket=bucket, record=points[i:i+500])

    anomalies = df["is_anomaly"].sum()
    log.info(f"{len(points)} puntos escritos en InfluxDB ({anomalies} anomalias marcadas)")

    # --- Supabase cloud (solo registros no-normales para ahorrar espacio) ---
    try:
        from ingestion.supabase_writer import write_anomalies_batch
        records = []
        for ts, row in df.iterrows():
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts_str = ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            records.append({
                "ts":            ts_str,
                "residual_mw":   float(row.get("residual_mw", 0)),
                "z_score":       float(row.get("z_score", 0)),
                "iforest_score": float(row.get("iforest_score", 0)),
                "is_anomaly":    int(row.get("is_anomaly", 0)),
                "nivel":         row.get("nivel", "normal"),
            })
        write_anomalies_batch(records)
        log.info(f"{len(records)} puntos escritos en Supabase (anomalies)")
    except Exception as e:
        log.warning(f"Supabase anomalies write falló (no critico): {e}")


# ---------------------------------------------------------------------------
# Informe en consola
# ---------------------------------------------------------------------------

def print_report(df: pd.DataFrame) -> None:
    """Imprime un resumen de las anomalías detectadas."""
    total   = len(df)
    alta    = (df["nivel"] == "alta").sum()
    media   = (df["nivel"] == "media").sum()
    anomaly = df["is_anomaly"].sum()

    print("\n" + "="*62)
    print("  INFORME DE DETECCION DE ANOMALIAS — Gemelo Digital")
    print("="*62)
    print(f"  Periodo analizado : {df.index.min().strftime('%Y-%m-%d %H:%M')} -> "
          f"{df.index.max().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Registros totales : {total}")
    print(f"  Anomalias detectadas: {anomaly} ({anomaly/total*100:.1f}%)")
    print(f"    Alta confianza  : {alta}")
    print(f"    Media confianza : {media}")
    print("-"*62)

    if alta + media > 0:
        top = (
            df[df["is_anomaly"]]
            .sort_values("z_score", key=abs, ascending=False)
            .head(10)
        )
        print("  Top anomalias (por |Z-score|):")
        print(f"  {'Timestamp':<22} {'Demanda':>9} {'Predicha':>9} {'Residuo':>9} {'Z':>7} {'Nivel':<8}")
        print("  " + "-"*58)
        for ts, row in top.iterrows():
            print(f"  {str(ts)[:19]:<22} "
                  f"{row['demand_mw']:>8.0f}MW "
                  f"{row['yhat']:>8.0f}MW "
                  f"{row['residual_mw']:>+8.0f}MW "
                  f"{row['z_score']:>+6.2f} "
                  f"{row['nivel']:<8}")
    else:
        print("  No se detectaron anomalias en el periodo analizado.")
    print("="*62 + "\n")


# ---------------------------------------------------------------------------
# Visualización
# ---------------------------------------------------------------------------

def plot_anomalies(df: pd.DataFrame) -> None:
    """Muestra gráfico de demanda con anomalías marcadas."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # --- Panel superior: demanda real vs predicha ---
    ax1 = axes[0]
    ax1.plot(df.index, df["demand_mw"], color="steelblue", linewidth=1,
             alpha=0.8, label="Demanda real")
    ax1.plot(df.index, df["yhat"], color="gray", linewidth=1, linestyle="--",
             alpha=0.6, label="Prediccion Prophet")

    # Marcar anomalías de alta confianza (rojo)
    mask_alta = df["nivel"] == "alta"
    if mask_alta.any():
        ax1.scatter(df.index[mask_alta], df.loc[mask_alta, "demand_mw"],
                    color="red", s=60, zorder=5, label=f"Anomalia alta ({mask_alta.sum()})")

    # Marcar anomalías de media confianza (naranja)
    mask_media = df["nivel"] == "media"
    if mask_media.any():
        ax1.scatter(df.index[mask_media], df.loc[mask_media, "demand_mw"],
                    color="orange", s=40, zorder=4, label=f"Anomalia media ({mask_media.sum()})")

    ax1.set_ylabel("Demanda (MW)")
    ax1.set_title("Deteccion de anomalias — Demanda electrica peninsular")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # --- Panel inferior: Z-score ---
    ax2 = axes[1]
    ax2.axhline(y=Z_THRESHOLD,  color="red",    linestyle="--", alpha=0.5, label=f"+{Z_THRESHOLD}")
    ax2.axhline(y=-Z_THRESHOLD, color="red",    linestyle="--", alpha=0.5, label=f"-{Z_THRESHOLD}")
    ax2.axhline(y=0,            color="black",  linestyle="-",  alpha=0.3)
    ax2.fill_between(df.index, df["z_score"], 0,
                     where=df["z_score"] > Z_THRESHOLD, color="red",    alpha=0.3)
    ax2.fill_between(df.index, df["z_score"], 0,
                     where=df["z_score"] < -Z_THRESHOLD, color="red",   alpha=0.3)
    ax2.plot(df.index, df["z_score"], color="purple", linewidth=0.8, alpha=0.7)
    ax2.set_ylabel("Z-score residuo")
    ax2.set_xlabel("Fecha")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.3)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%Hh"))
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), "../analysis/04_anomalias_detectadas.png"),
                dpi=150, bbox_inches="tight")
    log.info("Grafico guardado: analysis/04_anomalias_detectadas.png")
    plt.show()


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Detector de anomalias en demanda electrica")
    parser.add_argument("--hours",  type=int, default=168,  help="Horas a analizar (def: 168 = 7d)")
    parser.add_argument("--plot",   action="store_true",    help="Mostrar grafico")
    parser.add_argument("--report", action="store_true",    help="Imprimir informe en consola")
    parser.add_argument("--no-save", action="store_true",   help="No escribir en InfluxDB")
    args = parser.parse_args()

    # 1. Cargar datos y modelo
    model = load_model()
    df    = load_data(hours=args.hours)

    # 2. Calcular residuos y detectar anomalías
    df = compute_prophet_residuals(model, df)
    df = detect_zscore(df)
    df = detect_isolation_forest(df)
    df = classify_anomalies(df)

    # 3. Guardar en InfluxDB
    if not args.no_save:
        save_anomalies(df)

    # 4. Informe y gráfico opcionales
    if args.report:
        print_report(df)

    if args.plot:
        plot_anomalies(df)

    if not args.report and not args.plot:
        # Resumen mínimo siempre visible
        alta  = (df["nivel"] == "alta").sum()
        media = (df["nivel"] == "media").sum()
        log.info(f"Analisis completado: {alta} anomalias alta confianza | {media} media confianza")


if __name__ == "__main__":
    main()
