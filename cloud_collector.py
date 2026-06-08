"""
cloud_collector.py — Colector ligero para GitHub Actions / entornos sin InfluxDB.

Estrategia de ingesta sin huecos (watermark):
  - Consulta el ultimo timestamp en Supabase para cada tabla.
  - Calcula cuantas horas hay que pedir para llegar hasta 'ahora'.
  - Anade un overlap de seguridad (OVERLAP_HOURS) para cubrir bordes.
  - Se auto-recupera: si la tabla lleva horas o dias sin datos,
    pide todo lo que falta (hasta MAX_HOURS_BACK).

Solo escribe en Supabase. No requiere InfluxDB local.
Dependencias: httpx supabase python-dotenv
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from ingestion.openmeteo import fetch_recent_weather
from ingestion.ree import fetch_demand, fetch_demand_synthetic
from ingestion.supabase_writer import _get_client, write_weather_batch, write_energy_batch
from ingestion.validators import filter_weather, filter_energy

# Cuantas horas extra pedir por encima del gap real (cubre retrasos del borde)
OVERLAP_HOURS = 2
# Maximo de horas a recuperar en una sola ejecucion (evita peticiones gigantes
# en el primer arranque o tras una interrupcion larga)
MAX_HOURS_BACK = 48


def _hours_to_fetch(table: str) -> int:
    """
    Calcula cuantas horas pedir para no dejar ningun hueco en 'table'.

    Logica:
      1. Consulta el MAX(ts) de la tabla en Supabase.
      2. Calcula gap = ahora - MAX(ts).
      3. Devuelve min(gap + OVERLAP_HOURS + 1, MAX_HOURS_BACK).

    Si la tabla esta vacia o la consulta falla, devuelve MAX_HOURS_BACK
    para hacer un llenado inicial completo.
    """
    try:
        client = _get_client()
        res = client.table(table).select('ts').order('ts', desc=True).limit(1).execute()
        if res.data:
            last_ts = datetime.fromisoformat(res.data[0]['ts'].replace('Z', '+00:00'))
            gap_h   = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
            hours   = int(gap_h) + OVERLAP_HOURS + 1
            return min(hours, MAX_HOURS_BACK)
    except Exception as e:
        print(f"  [watermark] No se pudo leer ultimo ts de '{table}': {e}", file=sys.stderr)
    return MAX_HOURS_BACK


def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== cloud_collector {now_str} ===")

    # -- Clima ------------------------------------------------------------------
    # Watermark: pide exactamente desde el ultimo dato hasta ahora + overlap.
    # fetch_recent_weather usa past_hours de Open-Meteo (sin lag de archivo).
    # La API acepta hasta 92h; nuestro MAX_HOURS_BACK=48 queda bien dentro.
    try:
        hours_w = _hours_to_fetch('weather')
        print(f"[CLIMA] Solicitando {hours_w}h (ultimo dato + {OVERLAP_HOURS}h overlap)")
        weather_records = fetch_recent_weather(hours_back=min(hours_w, 90))
        weather_records, w_rejected = filter_weather(weather_records)
        if w_rejected:
            print(f"[CLIMA] Rechazados {len(w_rejected)} registros fuera de rango:", file=sys.stderr)
            for r in w_rejected[:3]:
                print(f"  {r}", file=sys.stderr)
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

    # -- Energia ----------------------------------------------------------------
    # Watermark: misma logica. Si GitHub Actions se retraso 5h, pedira 5+2+1=8h.
    # Si no habia datos (primer arranque), pedira MAX_HOURS_BACK=48h.
    # Upsert por ts evita duplicados en el overlap.
    try:
        hours_e = _hours_to_fetch('energy')
        print(f"[ENERGIA] Solicitando {hours_e}h (ultimo dato + {OVERLAP_HOURS}h overlap)")
        records = fetch_demand(hours_back=hours_e)
        source  = "ree_real"
        if not records:
            records = fetch_demand_synthetic(hours_back=hours_e)
            source  = "synthetic"

        if records:
            records, e_rejected = filter_energy(records)
            if e_rejected:
                print(f"[ENERGIA] Rechazados {len(e_rejected)} registros fuera de rango:", file=sys.stderr)
                for r in e_rejected[:3]:
                    print(f"  {r}", file=sys.stderr)
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
