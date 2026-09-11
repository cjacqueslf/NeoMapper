import re
from pathlib import Path
from datetime import timezone, timedelta
from zoneinfo import ZoneInfo

try:
    from timezonefinder import TimezoneFinder
    HAS_TIMEZONEFINDER = True
except Exception:
    TimezoneFinder = None
    HAS_TIMEZONEFINDER = False

def safe_filename(text: str) -> str:
    text = (text or "object").strip().replace("(", "").replace(")", "")
    text = text.replace("/", "-").replace("\\", "-")
    text = re.sub(r"[^A-Za-z0-9_.+-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_") or "object"

def suggest_output_filename(object_text: str, utc_text: str, targetname: str | None = None) -> str:
    from astropy.time import Time
    designation = safe_filename(targetname or object_text or "object")
    value = utc_text.strip().replace(" ", "T")
    if len(value) == 16:
        value += ":00"
    t = Time(value, scale="utc")
    return f"{designation}_{t.utc.datetime:%Y-%m-%d}_{t.utc.datetime:%H%MUTC}.png"

def timezone_from_reference(lat: float, lon: float):
    if HAS_TIMEZONEFINDER:
        try:
            tf = TimezoneFinder()
            tz_name = tf.timezone_at(lat=float(lat), lng=float(lon))
            if tz_name:
                return tz_name, ZoneInfo(tz_name)
        except Exception:
            pass
    offset_hours = int(round(float(lon) / 15.0))
    offset_hours = max(-12, min(14, offset_hours))
    sign = "+" if offset_hours >= 0 else "-"
    return f"UTC{sign}{abs(offset_hours):02d}:00", timezone(timedelta(hours=offset_hours))

def format_time_for_map(t, mode: str, ref_lat: float, ref_lon: float):
    mode = (mode or "UTC").upper()
    dt_utc = t.utc.datetime.replace(tzinfo=timezone.utc)
    if mode == "LOCAL":
        tz_name, tzinfo = timezone_from_reference(ref_lat, ref_lon)
        dt_local = dt_utc.astimezone(tzinfo)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S"), "LOCAL"
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S"), "UTC"

def minutes_from_step_label(label: str) -> int:
    """
    Converte labels da GUI em minutos.
    Aceita EN/PT e também valores numéricos.
    """
    label = (label or "5").lower().strip()
    if "day" in label or "dia" in label:
        m = re.search(r"(\d+)", label)
        return int(m.group(1)) * 1440 if m else 1440
    if "hour" in label or "hora" in label:
        m = re.search(r"(\d+)", label)
        return int(m.group(1)) * 60 if m else 60
    m = re.search(r"(\d+)", label)
    return int(m.group(1)) if m else 5


def minutes_from_duration(value: str, unit: str = "hours") -> int:
    try:
        n = float(value)
    except Exception:
        n = 4.0
    unit = (unit or "hours").lower()
    if unit in ("minutes", "minutos", "minute", "minuto"):
        return max(1, int(round(n)))
    if unit in ("days", "dias", "day", "dia"):
        return max(1, int(round(n * 1440)))
    return max(1, int(round(n * 60)))


def parse_input_time_for_mode(text: str, mode: str, ref_lat: float, ref_lon: float):
    """Parse GUI input according to the selected time display mode and return astropy Time in UTC."""
    from astropy.time import Time
    from datetime import timezone
    value = (text or "").strip().replace("T", " ")
    if len(value) == 16:
        value += ":00"
    mode_key = (mode or "UTC").strip().upper()
    # The GUI may provide translated labels such as "Hora local".
    is_local = mode_key == "LOCAL" or "LOCAL" in mode_key or "LOCAl" in mode_key
    if is_local:
        tz_name, tzinfo = timezone_from_reference(ref_lat, ref_lon)
        from datetime import datetime
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=tzinfo)
        return Time(dt.astimezone(timezone.utc))
    return Time(value, scale="utc")
