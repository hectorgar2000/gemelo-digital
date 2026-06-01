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

from ingestion.openmeteo import fetch_current_weather
from ingestion.ree import fetch_demand, fetch_demand_synthetic
from ingestion.supabase_writer import write_weather, write_energy


def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== cloud_collector {now_str} ===")

    # -- Clima ------------------------------------------------------------------
    try:
        weather = fetch_current_weather()
        write_weather(weather)
        print(
            f"[CLIMA] T={weather['temperature_c']}C  "
            f"H={weather['humidity_pct']}%  "
            f"Sol={weather['solar_radiation_wm2']}W/m2  OK"
        )
    except Exception as e:
        print(f"[CLIMA] Error: {e}", file=sys.stderr)

    # -- Energía ----------------------------------------------------------------
    try:
        records = fetch_demand(hours_back=2)
        source = "ree_real"
        if not records:
            records = fetch_demand_synthetic(hours_back=1)
            source = "synthetic"

        if records:
            latest = records[-1]
            write_energy(latest, source=source)
            print(f"[ENERGIA] {latest['demand_mw']:.0f} MW  (fuente: {source})  OK")
        else:
            print("[ENERGIA] Sin datos en este ciclo")
    except Exception as e:
        print(f"[ENERGIA] Error: {e}", file=sys.stderr)

    print("=== cloud_collector completado ===")


if __name__ == "__main__":
    main()
