"""Distance display preferences; numerical model values keep their units."""
from __future__ import annotations

from astropy import units as u
from matplotlib.text import Text
from neomapper.presentation.i18n import format_number, normalize_locale

AU_KM = u.au.to(u.km)


def format_distance(distance_km: float | None, unit: str = "km", language: str = "EN") -> str:
    if distance_km is None:
        return "—"
    if unit.upper() in ("UA", "AU"):
        label = "AU" if normalize_locale(language).startswith("en") else "UA"
        value = float(distance_km) / AU_KM
        decimals = 9 if 0 < abs(value) < 0.000001 else 6
        return f"{format_number(value, decimals, language)} {label}"
    return f"{format_number(distance_km, 0, language)} km"


def figure_distance(figure, distance_km: float, unit: str, language: str) -> str:
    text = format_distance(distance_km, unit, language)
    entries = getattr(figure, "_distance_labels", [])
    entries.append((distance_km, text, language))
    figure._distance_labels = entries
    return text


def update_figure_distances(figure, unit: str) -> None:
    entries = getattr(figure, "_distance_labels", [])
    updated = [(km, format_distance(km, unit, language), language) for km, _, language in entries]
    for artist in figure.findobj(match=Text):
        text = artist.get_text()
        for (_, old, _), (_, new, _) in zip(entries, updated):
            text = text.replace(old, new)
        artist.set_text(text)
    figure._distance_labels = updated
