"""
collector.py — Orquestador principal de ingestión de datos.

Recoge datos de Open-Meteo y REE/ESIOS cada 10 minutos
y los escribe en InfluxDB.

Uso:
    python collector.py               # producción (bucle infinito)
    python collector.py --once        # ejecutar una sola vez y salir
    python collector.py --backfill 48 # rellenar las últimas 48h de histórico
"""

import argparse
import logging
import sys
import os
import schedule
import time
from datetime import datetime, timezone

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(__file__))

from ingestion.openmeteo import fetch_current_weather, fetch_recent_weather, fetch_historical_weather
from ingestion.ree import (fetch_demand, fetch_demand_real_range,
                            fetch_demand_synthetic, generate_demand_from_weather_records)
from ingestion.influx_writer import write_weather, write_energy, write_weather_batch, write_energy_batch

# Supabase dual-write (opcional — no interrumpe si falla)
try:
    from ingestion.supabase_writer import (
        _get_client         as sb_get_client,
        write_weather       as sb_write_weather,
        write_energy        as sb_write_energy,
        write_weather_batch as sb_write_weather_batch,
        write_energy_batch  as sb_write_energy_batch,
    )
    HAS_SUPABASE = True
except Exception as _sb_err:
    HAS_SUPABASE = False

# Parametros de la estrategia watermark
OVERLAP_HOURS  = 2   # horas extra sobre el gap real (cubre bordes y retrasos)
MAX_HOURS_BACK = 48  # maximo a pedir en una sola ejecucion

# --- Logging ----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("collector.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# --- Watermark --------------------------------------------------------------

def _hours_to_fetch(table: str, fallback: int = MAX_HOURS_BACK) -> int:
    """
    Calcula cuantas horas pedir para no dejar ningun hueco en 'table'.

    Si Supabase esta disponible, consulta el ultimo timestamp y devuelve
    gap_real + OVERLAP_HOURS + 1. Si no, usa el fallback fijo.
    """
    if HAS_SUPABASE:
        try:
            client = sb_get_client()
            res    = client.table(table).select('ts').order('ts', desc=True).limit(1).execute()
            if res.data:
                last_ts = datetime.fromisoformat(res.data[0]['ts'].replace('Z', '+00:00'))
                gap_h   = (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600
                return min(int(gap_h) + OVERLAP_HOURS + 1, MAX_HOURS_BACK)
        except Exception as e:
            log.warning(f"[watermark] No se pudo leer '{table}' de Supabase: {e}")
    return fallback


# --- Tarea principal --------------------------------------------------------

def collect_once() -> None:
    """Recoge un ciclo completo de datos y los escribe en InfluxDB."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log.info(f"=== Ciclo de recoleccion iniciado: {now_str} ===")

    # -- Clima ---------------------------------------------------------------
    # Watermark: pide exactamente desde el ultimo dato hasta ahora + overlap.
    # fetch_recent_weather usa past_hours de Open-Meteo (sin lag de archivo).
    # Upsert por 'ts' evita duplicados en InfluxDB y Supabase.
    try:
        hours_w = _hours_to_fetch('weather')
        log.info(f"[CLIMA] Solicitando {hours_w}h (watermark + {OVERLAP_HOURS}h overlap)")
        weather_records = fetch_recent_weather(hours_back=min(hours_w, 90))
        write_weather_batch(weather_records)
        if HAS_SUPABASE:
            try:
                sb_write_weather_batch(weather_records)
            except Exception as e:
                log.warning(f"[CLIMA Supabase] {e}")
        latest_w = weather_records[-1] if weather_records else {}
        log.info(
            f"[CLIMA]  T={latest_w.get('temperature_c')}C  "
            f"H={latest_w.get('humidity_pct')}%  "
            f"Viento={latest_w.get('wind_speed_kmh')}km/h  "
            f"Sol={latest_w.get('solar_radiation_wm2')}W/m2  "
            f"({len(weather_records)} puntos)"
        )
    except Exception as e:
        log.error(f"[CLIMA] Error: {e}")

    # -- Energía — API pública REE (sin token) --------------------------------
    # Watermark: misma logica. Upsert evita duplicados.
    try:
        hours_e = _hours_to_fetch('energy')
        log.info(f"[ENERGIA] Solicitando {hours_e}h (watermark + {OVERLAP_HOURS}h overlap)")
        records = fetch_demand(hours_back=hours_e)
        source  = "ree_real" if records else "synthetic"
        if not records:
            records = fetch_demand_synthetic(hours_back=hours_e)

        if records:
            latest = records[-1]
            write_energy_batch(records, source=source)
            if HAS_SUPABASE:
                try:
                    sb_write_energy_batch(records, source=source)
                except Exception as e:
                    log.warning(f"[ENERGIA Supabase] {e}")
            log.info(f"[ENERGIA] {latest['demand_mw']:.0f} MW  ({len(records)} pts, fuente: {source})")
        else:
            log.warning("[ENERGIA] Sin datos en este ciclo")
    except Exception as e:
        log.error(f"[ENERGIA] Error: {e}")

    log.info("=== Ciclo completado ===")


# --- Backfill ---------------------------------------------------------------

def backfill(hours: int) -> None:
    """
    Rellena InfluxDB con datos históricos de las últimas N horas.
    - El clima se obtiene de Open-Meteo (datos reales, hasta 10 años atrás).
    - La energía se genera a partir de la temperatura real (correlación genuina)
      o de ESIOS si hay token disponible.
    """
    from datetime import timedelta
    log.info(f"Iniciando backfill de {hours}h ({hours//24} dias)...")

    end   = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    # -- Clima real ----------------------------------------------------------
    weather_records = []
    try:
        # Open-Meteo acepta rangos de hasta 10 años en la API de archivo
        weather_records = fetch_historical_weather(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )
        write_weather_batch(weather_records)
        if HAS_SUPABASE:
            try:
                sb_write_weather_batch(weather_records)
                log.info(f"[CLIMA backfill Supabase] {len(weather_records)} registros escritos")
            except Exception as e:
                log.warning(f"[CLIMA backfill Supabase] {e}")
        log.info(f"[CLIMA backfill] {len(weather_records)} registros escritos")
    except Exception as e:
        log.error(f"[CLIMA backfill] Error: {e}")

    # -- Energía — datos reales REE API pública -------------------------------
    try:
        log.info("[ENERGIA backfill] Descargando demanda real de REE API publica...")
        energy_records = fetch_demand_real_range(start, end, chunk_days=7)
        source = "ree_real"

        if not energy_records:
            log.warning("[ENERGIA backfill] API REE sin datos — usando sintético correlacionado")
            energy_records = (
                generate_demand_from_weather_records(weather_records)
                if weather_records else fetch_demand_synthetic(hours_back=hours)
            )
            source = "synthetic"

        write_energy_batch(energy_records, source=source)
        if HAS_SUPABASE:
            try:
                sb_write_energy_batch(energy_records, source=source)
                log.info(f"[ENERGIA backfill Supabase] {len(energy_records)} registros escritos")
            except Exception as e:
                log.warning(f"[ENERGIA backfill Supabase] {e}")
        log.info(f"[ENERGIA backfill] {len(energy_records)} registros escritos (fuente: {source})")
    except Exception as e:
        log.error(f"[ENERGIA backfill] Error: {e}")

    log.info("Backfill completado.")


# --- Punto de entrada -------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Gemelo Digital — Colector de datos")
    parser.add_argument("--once",     action="store_true", help="Ejecutar una vez y salir")
    parser.add_argument("--backfill", type=int, metavar="HORAS",
                        help="Rellenar historico de las últimas N horas")
    args = parser.parse_args()

    if args.backfill:
        backfill(args.backfill)
        return

    if args.once:
        collect_once()
        return

    # Modo produccion: ejecutar ahora y luego cada 10 minutos
    log.info("Colector iniciado — intervalo: 10 minutos. Ctrl+C para detener.")
    collect_once()
    schedule.every(10).minutes.do(collect_once)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Colector detenido por el usuario.")


if __name__ == "__main__":
    main()
