"""Sexagesimal display of equatorial coordinates supplied in degrees."""
from __future__ import annotations

import math

from neomapper.presentation.i18n import format_number


def format_right_ascension(ra_deg: float | None, language: str = "EN") -> str:
    """Normalize RA to [0, 24h), including carry after rounding to 0.01s."""
    if ra_deg is None or not math.isfinite(ra_deg):
        return "-"
    ticks = round((ra_deg % 360.0) / 15.0 * 360000) % 8640000
    hours, remainder = divmod(ticks, 360000)
    minutes, seconds = divmod(remainder, 6000)
    second_text = format_number(seconds / 100, 2, language, grouping=False).zfill(5)
    return f"{hours:02d}h {minutes:02d}m {second_text}s"


def format_declination(dec_deg: float | None, language: str = "EN") -> str:
    """Preserve declination's sign (including negative zero), rounding to 0.01 arcsec."""
    if dec_deg is None or not math.isfinite(dec_deg):
        return "-"
    sign = "-" if math.copysign(1.0, dec_deg) < 0 else "+"
    degrees, remainder = divmod(round(abs(dec_deg) * 360000), 360000)
    minutes, seconds = divmod(remainder, 6000)
    second_text = format_number(seconds / 100, 2, language, grouping=False).zfill(5)
    return f"{sign}{degrees:02d}° {minutes:02d}' {second_text}\""
