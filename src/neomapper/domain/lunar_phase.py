"""Geometric lunar illumination from airless observer-relative directions."""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class LunarAppearance:
    illuminated_fraction: float
    limb_azimuth_deg: float
    limb_altitude_deg: float


def lunar_appearance(moon_az_deg: float, moon_alt_deg: float, moon_distance_au: float,
                     sun_az_deg: float, sun_alt_deg: float, sun_distance_au: float) -> LunarAppearance:
    """Sphere lit by the Sun; limb point is a nearby direction toward the Sun.

    Distances share AU, azimuth is north through east, normalized to [0, 360).
    The projected lit fraction is (1 + cos(phase angle)) / 2. No eclipse model.
    """
    def direction(az_deg: float, alt_deg: float) -> np.ndarray:
        az, alt = np.radians([az_deg, alt_deg])
        return np.array([np.cos(alt) * np.cos(az), np.cos(alt) * np.sin(az), np.sin(alt)])

    moon = direction(moon_az_deg, moon_alt_deg)
    sun = direction(sun_az_deg, sun_alt_deg)
    light = sun * sun_distance_au - moon * moon_distance_au
    light /= np.linalg.norm(light)
    cosine = float(np.clip(np.dot(light, -moon), -1, 1))
    tangent = sun - np.dot(sun, moon) * moon
    norm = np.linalg.norm(tangent)
    if norm < 1e-12:
        # At exact conjunction/opposition limb orientation is immaterial.
        tangent = direction(moon_az_deg + 90, 0)
    else:
        tangent /= norm
    limb = moon + 1e-4 * tangent
    limb /= np.linalg.norm(limb)
    return LunarAppearance((1 + cosine) / 2,
                           math.degrees(math.atan2(limb[1], limb[0])) % 360,
                           math.degrees(math.asin(float(limb[2]))))
