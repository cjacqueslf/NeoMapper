"""Two-body osculating orbits in the reference frame of the input state."""
from __future__ import annotations

import numpy as np


def osculating_orbit(position_au: np.ndarray, velocity_au_day: np.ndarray,
                     mu_au3_day2: float, samples: int = 721) -> np.ndarray:
    """Sample the instantaneous bound ellipse, starting at the supplied position.

    This is a two-body visualization at one epoch, not a future ephemeris.
    The radial/transverse basis also supports circular and inclined orbits.
    """
    r = np.asarray(position_au, dtype=float)
    v = np.asarray(velocity_au_day, dtype=float)
    if r.shape != (3,) or v.shape != (3,) or not np.isfinite(r).all() or not np.isfinite(v).all() or not np.isfinite(mu_au3_day2):
        raise ValueError("Invalid orbital state")
    radius = np.linalg.norm(r)
    h = np.cross(r, v)
    h_norm = np.linalg.norm(h)
    if radius <= 0 or h_norm <= 0 or mu_au3_day2 <= 0 or samples < 3:
        raise ValueError("Invalid orbital state or sampling")
    radial = r / radius
    transverse = np.cross(h / h_norm, radial)
    e_vector = np.cross(v, h) / mu_au3_day2 - radial
    if np.linalg.norm(e_vector) >= 1:
        raise ValueError("A bound elliptic orbit is required")
    angles = np.linspace(0, 2 * np.pi, samples)
    directions = np.cos(angles)[:, None] * radial + np.sin(angles)[:, None] * transverse
    radii = (h_norm ** 2 / mu_au3_day2) / (1 + directions @ e_vector)
    return directions * radii[:, None]
