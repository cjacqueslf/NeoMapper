"""Localized target status shared by still charts and animation frames."""
from neomapper.domain.sky_brightness import target_visibility
from neomapper.presentation.i18n import Translator

STATUS_KEYS = {
    "sky_glare": "Obscured by sky brightness",
    "below_horizon": "Below the horizon",
    "above_horizon": "Above the horizon",
    "unknown_twilight": "Twilight: visibility unknown",
}


def target_status(sun_alt_deg: float, object_alt_deg: float, magnitude: float | None, language: str) -> str:
    code = target_visibility(sun_alt_deg, object_alt_deg, magnitude)
    return Translator(language).tr(STATUS_KEYS[code])
