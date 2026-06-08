"""
ingestion/validators.py — Validación de rangos para datos de ingesta.

Rechaza registros físicamente imposibles antes de escribirlos en Supabase.
Los rangos están calibrados para la red eléctrica peninsular española y
la climatología de Madrid.
"""

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

    humidity = record.get("humidity_pct")
    if humidity is not None:
        try:
            h = float(humidity)
            if not (HUMIDITY_MIN <= h <= HUMIDITY_MAX):
                return False, f"humidity_pct={h:.1f} fuera de [0, 100]"
        except (TypeError, ValueError):
            pass  # No es crítico

    wind = record.get("wind_speed_kmh")
    if wind is not None:
        try:
            w = float(wind)
            if w < 0 or w > WIND_MAX_KMH:
                return False, f"wind_speed_kmh={w:.1f} fuera de [0, {WIND_MAX_KMH}]"
        except (TypeError, ValueError):
            pass

    radiation = record.get("solar_radiation_wm2")
    if radiation is not None:
        try:
            r = float(radiation)
            if r < 0 or r > RADIATION_MAX_WM2:
                return False, f"solar_radiation_wm2={r:.1f} fuera de [0, {RADIATION_MAX_WM2}]"
        except (TypeError, ValueError):
            pass

    return True, ""


def filter_energy(records: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Filtra registros de energía inválidos.
    Devuelve (registros_válidos, lista_de_rechazos_con_razón).
    """
    valid, rejected = [], []
    for r in records:
        ok, reason = validate_energy_record(r)
        if ok:
            valid.append(r)
        else:
            rejected.append(f"{r.get('timestamp', '?')} → {reason}")
    return valid, rejected


def filter_weather(records: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Filtra registros meteorológicos inválidos.
    Devuelve (registros_válidos, lista_de_rechazos_con_razón).
    """
    valid, rejected = [], []
    for r in records:
        ok, reason = validate_weather_record(r)
        if ok:
            valid.append(r)
        else:
            rejected.append(f"{r.get('timestamp', '?')} → {reason}")
    return valid, rejected
