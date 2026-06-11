"""
cloud_model_eval.py — Evaluación diaria del modelo Prophet.

Compara las predicciones del forecast de las últimas 24h con la
demanda real registrada en el mismo período y calcula el MAPE y MAE.

Sale con exit code 1 si el MAPE supera MAPE_ALERT_THRESHOLD,
lo que hace que GitHub Actions notifique al propietario del repo.

Uso:
    python cloud_model_eval.py
    python cloud_model_eval.py --hours 48    # evaluar últimas 48h
    python cloud_model_eval.py --no-fail     # solo logging, nunca falla
"""

import os
import sys
import argparse
import numpy as np
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

# MAPE (%) a partir del cual se considera que el modelo necesita reentrenamiento
MAPE_ALERT_THRESHOLD = 10.0


def load_data(sb, hours: int) -> tuple[dict, dict]:
    """Carga forecast y energy del mismo rango horario."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    fc_res = (
        sb.table("forecast")
        .select("ts,demand_mw")
        .gte("ts", start.isoformat())
        .lt("ts",  end.isoformat())
        .order("ts")
        .execute()
    )
    real_res = (
        sb.table("energy")
        .select("ts,demand_mw")
        .gte("ts", start.isoformat())
        .lt("ts",  end.isoformat())
        .eq("source", "ree_real")   # solo comparar contra datos reales, no sintéticos
        .order("ts")
        .execute()
    )

    # Indexar por 'YYYY-MM-DDTHH' (hora UTC) para join robusto
    fc_map   = {r["ts"][:13]: r["demand_mw"] for r in (fc_res.data  or []) if r["demand_mw"]}
    real_map = {r["ts"][:13]: r["demand_mw"] for r in (real_res.data or []) if r["demand_mw"]}
    return fc_map, real_map


def compute_metrics(fc_map: dict, real_map: dict) -> dict:
    """Calcula MAPE, MAE y RMSE sobre las horas comunes."""
    common = sorted(set(fc_map.keys()) & set(real_map.keys()))
    if not common:
        return {}

    errors, pct_errors, sq_errors = [], [], []
    for hour in common:
        pred   = fc_map[hour]
        actual = real_map[hour]
        ae     = abs(pred - actual)
        errors.append(ae)
        pct_errors.append(ae / actual * 100)
        sq_errors.append((pred - actual) ** 2)

    return {
        "n_hours":    len(common),
        "mape":       float(np.mean(pct_errors)),
        "mae":        float(np.mean(errors)),
        "rmse":       float(np.sqrt(np.mean(sq_errors))),
        "max_error":  float(np.max(errors)),
        "first_hour": common[0],
        "last_hour":  common[-1],
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluacion diaria del modelo Prophet")
    parser.add_argument("--hours",   type=int,  default=24,  help="Horas a evaluar (def: 24)")
    parser.add_argument("--no-fail", action="store_true",    help="No salir con error aunque el MAPE sea alto")
    args = parser.parse_args()

    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_KEY requeridos", file=sys.stderr)
        sys.exit(1)

    sb = create_client(url, key)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== cloud_model_eval {now_str} (ventana={args.hours}h) ===")

    fc_map, real_map = load_data(sb, args.hours)
    print(f"  Forecast disponible: {len(fc_map)} horas")
    print(f"  Real disponible:     {len(real_map)} horas")

    if not fc_map or not real_map:
        # Sin datos no es un fallo del modelo — puede ser el primer día tras el despliegue
        # o que daily_forecast.yml aún no haya corrido. Salir con 0 para no generar
        # falsa alarma por email.
        print("INFO: datos insuficientes para evaluación (¿primer día tras deploy?). Sin alerta.")
        sys.exit(0)

    m = compute_metrics(fc_map, real_map)
    if not m:
        print("INFO: no hay horas coincidentes entre forecast y real. Sin alerta.")
        sys.exit(0)

    print(f"\n  Período:     {m['first_hour']} → {m['last_hour']}")
    print(f"  Horas eval:  {m['n_hours']}")
    print(f"  MAPE:        {m['mape']:.2f}%  ({'OK' if m['mape'] <= MAPE_ALERT_THRESHOLD else 'ALTO'})")
    print(f"  MAE:         {m['mae']:.0f} MW")
    print(f"  RMSE:        {m['rmse']:.0f} MW")
    print(f"  Error max:   {m['max_error']:.0f} MW")

    if m["mape"] > MAPE_ALERT_THRESHOLD:
        print(f"\nALERTA: MAPE {m['mape']:.1f}% > {MAPE_ALERT_THRESHOLD}%")
        print("  Considerar reentrenar el modelo: python prediction/forecast.py --retrain")
        if not args.no_fail:
            sys.exit(1)
    else:
        print(f"\nOK: MAPE {m['mape']:.1f}% dentro del umbral ({MAPE_ALERT_THRESHOLD}%)")


if __name__ == "__main__":
    main()
