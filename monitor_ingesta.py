"""
monitor_ingesta.py — Verifica que weather y energy tienen datos recientes.

Sale con exit code 1 si alguna tabla supera MAX_GAP_HOURS horas sin datos.
GitHub Actions marca el job como fallido → notificación por email al propietario.

Uso:
    python monitor_ingesta.py
    python monitor_ingesta.py --max-gap 6   # tolerar hasta 6h
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Gap maximo tolerable en horas antes de considerar la ingesta rota
DEFAULT_MAX_GAP = 3


def check_table(sb, table: str) -> float:
    """Devuelve las horas transcurridas desde el ultimo registro, o inf si esta vacia."""
    res = sb.table(table).select("ts").order("ts", desc=True).limit(1).execute()
    if not res.data:
        return float("inf")
    last_ts = datetime.fromisoformat(res.data[0]["ts"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - last_ts).total_seconds() / 3600


def main():
    parser = argparse.ArgumentParser(description="Monitor de frescura de datos")
    parser.add_argument("--max-gap", type=float, default=DEFAULT_MAX_GAP,
                        help=f"Gap maximo en horas (def: {DEFAULT_MAX_GAP})")
    args = parser.parse_args()

    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("[ERROR] SUPABASE_URL y SUPABASE_SERVICE_KEY son obligatorios", file=sys.stderr)
        sys.exit(1)

    sb = create_client(url, key)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== monitor_ingesta {now_str} (max_gap={args.max_gap}h) ===")

    failed = False
    for table in ["weather", "energy"]:
        gap = check_table(sb, table)
        if gap == float("inf"):
            print(f"[CRITICO] {table}: tabla VACIA — ingesta nunca ejecutada o datos borrados")
            failed = True
        elif gap > args.max_gap:
            print(f"[ERROR]   {table}: ultimo dato hace {gap:.1f}h (maximo {args.max_gap}h) — ingesta rota")
            failed = True
        else:
            print(f"[OK]      {table}: ultimo dato hace {gap:.1f}h")

    if failed:
        print("\nFALLO: uno o mas streams de datos estan desactualizados.")
        print("Revisar el workflow hourly_collect en GitHub Actions.")
        sys.exit(1)

    print("\nOK: todos los streams de datos son recientes.")


if __name__ == "__main__":
    main()
