"""
cloud_collector.py — Colector ligero para GitHub Actions / entornos sin InfluxDB.

Solo escribe en Supabase. No requiere InfluxDB local.
Dependencias: httpx supabase python-dotenv

Uso:
    python cloud_collector.py
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from ingestion.openmeteo import fetch_recent_weather
from ingestion.ree import fetch_demand, fetch_demand_synthetic
from ingestion.supabase_writer import write_weather_batch, write_energy_batch


def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== cloud_collector {now_str} ===")

    # -- Clima ------------------------------------------------------------------
    # Ventana de 6h: si GitHub Actions se retrasa o falla, la siguiente
    # ejecución recupera todos los puntos perdidos gracias al overlap.
    # fetch_recent_weather usa el parámetro past_hours de Open-Meteo
    # (sin el lag de 2-3 días del archivo histórico).
    # El upsert por 'ts' evita duplicados.
    try:
        weather_records = fetch_recent_weather(hours_back=6)
        write_weather_batch(weather_records)
        latest_w = weather_records[-1] if weather_records else {}
        print(
            f"[CLIMA] T={latest_w.get('temperature_c')}C  "
            f"H={latest_w.get('humidity_pct')}%  "
            f"Sol={latest_w.get('solar_radiation_wm2')}W/m2  "
            f"({len(weather_records)} puntos guardados)  OK"
        )
    except Exception as e:
        print(f"[CLIMA] Error: {e}", file=sys.stderr)

    # -- Energía ----------------------------------------------------------------
    # Ventana de 6h para garantizar overlap robusto con la ejecución anterior.
    # GitHub Actions puede retrasarse hasta 5h en el tier gratuito; con 6h
    # de overlap nunca se pierde un punto aunque fallen dos ejecuciones seguidas.
    # El upsert por 'ts' evita duplicados.
    try:
        records = fetch_demand(hours_back=6)
        source = "ree_real"
        if not records:
            records = fetch_demand_synthetic(hours_back=3)
            source = "synthetic"

        if records:
            write_energy_batch(records, source=source)
            latest = records[-1]
            print(
                f"[ENERGIA] {latest['demand_mw']:.0f} MW  "
                f"({len(records)} puntos guardados, fuente: {source})  OK"
            )
        else:
            print("[ENERGIA] Sin datos en este ciclo")
    except Exception as e:
        print(f"[ENERGIA] Error: {e}", file=sys.stderr)

    print("=== cloud_collector completado ===")


if __name__ == "__main__":
    main()
