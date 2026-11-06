"""
monitor_ingesta.py — Verifica que weather y energy tienen datos recientes.

Si alguna tabla supera MAX_GAP_HOURS horas sin datos:
  - Con --heal (por defecto en GitHub Actions) ejecuta el colector en el mismo
    proceso para recuperar el hueco y vuelve a comprobar. Solo falla si los
    datos siguen desactualizados tras la recuperación (ingesta realmente rota).
  - Sin --heal sale directamente con exit code 1.

Motivo del auto-healing: GitHub Actions retrasa o descarta ejecuciones
programadas del plan gratuito en horas de carga, así que hourly_collect.yml
puede pasar 4-8h sin ejecutarse aunque el código funcione. El colector usa
watermark, por lo que una ejecución tardía recupera todo el hueco sin pérdida.

Uso:
    python monitor_ingesta.py
    python monitor_ingesta.py --max-gap 6   # tolerar hasta 6h
    python monitor_ingesta.py --heal        # intentar recuperar antes de fallar
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Gap maximo tolerable en horas antes de considerar la ingesta rota
DEFAULT_MAX_GAP = 3
TABLES = ["weather", "energy"]


def _gh_annotation(level: str, msg: str) -> None:
    """Emite una anotación visible en la UI de GitHub Actions (no-op en local)."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::{level} title=Monitor de ingesta::{msg}")


def _gh_summary(lines: list[str]) -> None:
    """Escribe un resumen en la pestaña Summary del run de GitHub Actions."""
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def check_table(sb, table: str) -> float:
    """Devuelve las horas transcurridas desde el ultimo registro, o inf si esta vacia."""
    res = sb.table(table).select("ts").order("ts", desc=True).limit(1).execute()
    if not res.data:
        return float("inf")
    last_ts = datetime.fromisoformat(res.data[0]["ts"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600


def check_all(sb, max_gap: float) -> dict[str, float]:
    """Comprueba todas las tablas. Devuelve {tabla: gap_horas} de las que fallan."""
    stale: dict[str, float] = {}
    for table in TABLES:
        gap = check_table(sb, table)
        if gap == float("inf"):
            print(f"[CRITICO] {table}: tabla VACIA — ingesta nunca ejecutada o datos borrados")
            stale[table] = gap
        elif gap > max_gap:
            print(f"[ERROR]   {table}: ultimo dato hace {gap:.1f}h (maximo {max_gap}h)")
            stale[table] = gap
        else:
            print(f"[OK]      {table}: ultimo dato hace {gap:.1f}h")
    return stale


def run_collector() -> bool:
    """Ejecuta cloud_collector en el mismo proceso. Devuelve True si terminó sin error."""
    import cloud_collector
    try:
        cloud_collector.main()
        return True
    except SystemExit as e:
        return not e.code
    except Exception as e:  # noqa: BLE001 — queremos registrar cualquier fallo
        print(f"[HEAL] El colector lanzó una excepción: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Monitor de frescura de datos")
    parser.add_argument("--max-gap", type=float, default=DEFAULT_MAX_GAP,
                        help=f"Gap maximo en horas (def: {DEFAULT_MAX_GAP})")
    parser.add_argument("--heal", action="store_true",
                        help="Si hay datos desactualizados, ejecutar el colector y volver a comprobar")
    args = parser.parse_args()

    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("[ERROR] SUPABASE_URL y SUPABASE_SERVICE_KEY son obligatorios", file=sys.stderr)
        _gh_annotation("error", "Faltan los secrets SUPABASE_URL / SUPABASE_SERVICE_KEY")
        sys.exit(1)

    sb = create_client(url, key)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== monitor_ingesta {now_str} (max_gap={args.max_gap}h, heal={args.heal}) ===")

    stale = check_all(sb, args.max_gap)
    summary = [f"### Monitor de ingesta — {now_str}", ""]

    if stale and args.heal:
        detail = ", ".join(f"{t} ({g:.1f}h)" for t, g in stale.items())
        print(f"\n[HEAL] Datos desactualizados: {detail}. Ejecutando colector...")
        _gh_annotation("warning", f"Datos desactualizados ({detail}); recuperados con el colector")
        summary.append(f"- ⚠️ Datos desactualizados antes de recuperar: {detail}")
        collector_ok = run_collector()
        print(f"[HEAL] Colector {'OK' if collector_ok else 'con errores'}. Re-comprobando...\n")
        stale = check_all(sb, args.max_gap)

    if stale:
        detail = ", ".join(f"{t} ({g:.1f}h)" for t, g in stale.items())
        print("\nFALLO: uno o mas streams de datos estan desactualizados.")
        print("Revisar el workflow hourly_collect y la disponibilidad de REE / Open-Meteo.")
        _gh_annotation("error", f"Ingesta rota: {detail}")
        summary.append(f"- ❌ Ingesta rota: {detail}")
        _gh_summary(summary)
        sys.exit(1)

    print("\nOK: todos los streams de datos son recientes.")
    summary.append("- ✅ Todos los streams de datos son recientes")
    _gh_summary(summary)


if __name__ == "__main__":
    main()
