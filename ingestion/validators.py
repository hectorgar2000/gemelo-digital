"""
ingestion/validators.py — Validación de rangos para datos de ingesta.

Rechaza registros físicamente imposibles antes de escribirlos en Supabase.
Los rangos están calibrados para la red eléctrica peninsular española y
la climatología de Madrid.
"""

from collections.abc import Callable

# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------

# Demanda eléctrica peninsular (MW)
ENERGY_MIN_MW = 14_000   # mínimo histórico (madrugada de agosto, festivo)
ENERGY_MAX_MW = 46_000   # máximo histórico (ola de calor + día laboral)

# Temperatura en Madrid (°C)
TEMP_MIN_C = -10.0       # episodio Filomena (enero 2021)
TEMP_MAX_C =  45.0       # récord verano (zona del área metropolitana)

# Humedad relativa
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0

# Viento (km/h) — descartar sensores rotos
WIND_MAX_KMH = 250.0

# Radiación solar (W/m²) — máximo físico a nivel del suelo
RADIATION_MAX_WM2 = 1400.0

# Campos opcionales meteorológicos: (clave, mínimo, máximo)
_OPTIONAL_RANGES: list[tuple[str, float, float]] = [
    ("humidity_pct",        HUMIDITY_MIN, HUMIDITY_MAX),
    ("wind_speed_kmh",      0.0,          WIND_MAX_KMH),
    ("solar_radiation_wm2", 0.0,          RADIATION_MAX_WM2),
]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _check_optional_range(record: dict, key: str, lo: float, hi: float) -> tuple[bool, str]:
    """
    Valida un campo numérico opcional en [lo, hi].
    Si el campo es None o no es parseable (no crítico), devuelve (True, '').
    """
    val = record.get(key)
    if val is None:
        return True, ""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return True, ""   # campo no crítico, no rechazar el registro
    if not (lo <= v <= hi):
        return False, f"{key}={v} fuera de [{lo}, {hi}]"
    return True, ""


def _filter_records(
    records: list[dict],
    validate_fn: Callable[[dict], tuple[bool, str]],
) -> tuple[list[dict], list[str]]:
    """
    Aplica validate_fn a cada registro.
    Devuelve (registros_válidos, lista_de_rechazos_con_razón).
    """
    valid: list[dict] = []
    rejected: list[str] = []
    for r in records:
        ok, reason = validate_fn(r)
        if ok:
            valid.append(r)
        else:
            rejected.append(f"{r.get('timestamp', '?')} → {reason}")
    return valid, rejected


# ---------------------------------------------------------------------------
# Validadores públicos
# ---------------------------------------------------------------------------

def validate_energy_record(record: dict) -> tuple[bool, str]:
    """
    Valida un registro de energía.
    Devuelve (válido, razón_si_inválido).
    """
    demand = record.get("demand_mw")
    if demand is None:
        return False, "demand_mw es None"
    try:
        d = float(demand)
    except (TypeError, ValueError):
        return False, f"demand_mw no es numérico: {demand!r}"
    if not (ENERGY_MIN_MW <= d <= ENERGY_MAX_MW):
        return False, f"demand_mw={d:.0f} fuera de [{ENERGY_MIN_MW}, {ENERGY_MAX_MW}]"
    return True, ""


def validate_weather_record(record: dict) -> tuple[bool, str]:
    """
    Valida un registro meteorológico.
    Devuelve (válido, razón_si_inválido).
    """
    temp = record.get("temperature_c")
    if temp is None:
        return False, "temperature_c es None"
    try:
        t = float(temp)
    except (TypeError, ValueError):
        return False, f"temperature_c no es numérico: {temp!r}"
    if not (TEMP_MIN_C <= t <= TEMP_MAX_C):
        return False, f"temperature_c={t:.1f} fuera de [{TEMP_MIN_C}, {TEMP_MAX_C}]"

    for key, lo, hi in _OPTIONAL_RANGES:
        ok, reason = _check_optional_range(record, key, lo, hi)
        if not ok:
            return False, reason

    return True, ""


# ---------------------------------------------------------------------------
# Filtros públicos
# ---------------------------------------------------------------------------

def filter_energy(records: list[dict]) -> tuple[list[dict], list[str]]:
    """Filtra registros de energía inválidos."""
    return _filter_records(records, validate_energy_record)


def filter_weather(records: list[dict]) -> tuple[list[dict], list[str]]:
    """Filtra registros meteorológicos inválidos."""
    return _filter_records(records, validate_weather_record)
