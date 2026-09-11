"""Heuristic clear-sky twilight display, not an instrument detection model.

Twilight boundaries: https://aa.usno.navy.mil/faq/RST_defs
Magnitude anchors are visualization choices, not USNO measured limits.
Clouds, lunar glare, light pollution, elongation and instrument sensitivity
are deliberately not modeled. Geometric solar altitude is in degrees.
"""
from __future__ import annotations

import numpy as np


def twilight_magnitude_limit(sun_alt_deg: float) -> float:
    return float(np.interp(sun_alt_deg, [-18., -12., -6., 0.], [7., 4.5, 1.5, -4.]))


def atmospheric_magnitude(magnitude, altitude_deg):
    sin_alt = np.maximum(np.sin(np.radians(np.maximum(altitude_deg, 0))), .001)
    airmass = 1. / (sin_alt + .025 * np.exp(-11. * sin_alt))
    return np.asarray(magnitude) + .18 * np.maximum(airmass - 1., 0)


def star_visibility(magnitude, altitude_deg, sun_alt_deg: float, configured_limit: float = 7.):
    """Opacity in [0,1]; brighter stars appear first, symmetrically at dawn/dusk."""
    apparent = atmospheric_magnitude(magnitude, altitude_deg)
    # A half-magnitude blend prevents stars popping into animation frames.
    limit = twilight_magnitude_limit(sun_alt_deg)
    opacity = np.clip((limit - apparent) / .5, 0., 1.)
    # Restore the entire configured catalogue at full astronomical darkness.
    night_blend = np.clip((-sun_alt_deg - 17.) / 1., 0., 1.)
    opacity = opacity + (1. - opacity) * night_blend
    return np.where((np.asarray(altitude_deg) > 0) & (apparent <= configured_limit)
                    & (sun_alt_deg < 0), opacity, 0.)


def milky_way_visibility(sun_alt_deg: float) -> float:
    return float(np.clip((-sun_alt_deg - 12.) / 6., 0., 1.))


def target_visibility(sun_alt_deg: float, object_alt_deg: float, magnitude: float | None) -> str:
    """Reason codes avoid claiming that every above-horizon target is observable."""
    if object_alt_deg < 0:
        return "below_horizon"
    if sun_alt_deg >= 0:
        return "sky_glare"
    if sun_alt_deg > -18:
        if magnitude is None or not np.isfinite(magnitude):
            return "unknown_twilight"
        if atmospheric_magnitude(magnitude, object_alt_deg) > twilight_magnitude_limit(sun_alt_deg):
            return "sky_glare"
    return "above_horizon"
