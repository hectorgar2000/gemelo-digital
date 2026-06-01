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

from ingestion.openmeteo import fetch_current_weather, fetch_historical_weather
from ingestion.ree import (fetch_demand, fetch_demand_real_range,
                            fetch_demand_synthetic, generate_demand_from_weather_records)
from ingestion.influx_writer import write_weather, write_energy, write_weather_batch, write_energy_batch

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


# --- Tarea principal --------------------------------------------------------

def collect_once() -> None:
    """Recoge un ciclo completo de datos y los escribe en InfluxDB."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log.info(f"=== Ciclo de recoleccion iniciado: {now_str} ===")

    # -- Clima ---------------------------------------------------------------
    try:
        weather = fetch_current_weather()
        write_weather(weather)
        log.info(
            f"[CLIMA]  T={weather['temperature_c']}C  "
            f"H={weather['humidity_pct']}%  "
            f"Viento={weather['wind_speed_kmh']}km/h  "
            f"Sol={weather['solar_radiation_wm2']}W/m2"
        )
    except Exception as e:
        log.error(f"[CLIMA] Error: {e}")

    # -- Energía — API pública REE (sin token) --------------------------------
    try:
        records = fetch_demand(hours_back=2)   # últimas 2h para asegurar al menos 1 punto
        source  = "ree_real" if records else "synthetic"
        if not records:
            records = fetch_demand_synthetic(hours_back=1)

        if records:
            latest = records[-1]
            write_energy(latest, source=source)
            log.info(f"[ENERGIA] {latest['demand_mw']:.0f} MW  (fuente: {source})")
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
        log.info(f"[CLIMA backfill] {len(weather_records)} registros escritos")
    except Exception as e:
        log.error(f"[CLIMA backfill] Error: {e}")

    # -- Energía — datos reales REE API pública -------------------------------
    try:
        log.info("[ENERGIA backfill] Descargando demanda real de REE API publica...")
        energy_records = fetch_demand_real_range(start, end, chunk_days=30)
        source = "ree_real"

        if not energy_records:
            log.warning("[ENERGIA backfill] API REE sin datos — usando sintético correlacionado")
            energy_records = (
                generate_demand_from_weather_records(weather_records)
                if weather_records else fetch_demand_synthetic(hours_back=hours)
            )
            source = "synthetic"

        write_energy_batch(energy_records, source=source)
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
