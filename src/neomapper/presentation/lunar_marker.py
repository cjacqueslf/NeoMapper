"""Draw a phase-aware lunar disk, oriented toward the Sun on the sky map."""
from __future__ import annotations

import numpy as np
from matplotlib.axes import Axes
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from neomapper.domain.lunar_phase import lunar_appearance


def phase_disk(fraction: float, angle_rad: float, size: int = 128) -> np.ndarray:
    """Rasterize a spherical terminator; angle is counterclockwise on screen."""
    y, x = np.mgrid[1:-1:complex(size), -1:1:complex(size)]
    radius2 = x*x + y*y
    z = np.sqrt(np.clip(1 - radius2, 0, 1))
    cosine = 2 * fraction - 1
    towards_light = x * np.cos(angle_rad) + y * np.sin(angle_rad)
    lit = towards_light * np.sqrt(max(0, 1 - cosine*cosine)) + z * cosine >= 0
    pixels = np.zeros((size, size, 4))
    pixels[:, :, :3] = np.where(lit[:, :, None], np.array([.91, .93, .95]), np.array([.10, .13, .17]))
    pixels[:, :, 3] = radius2 <= 1
    return pixels


def draw_moon(ax: Axes, moon: dict, sun: dict) -> AnnotationBbox:
    appearance = lunar_appearance(moon["az"], moon["alt"], moon["distance_au"],
                                 sun["az"], sun["alt"], sun["distance_au"])
    center = (np.radians(moon["az"]), 90 - moon["alt"])
    limb = (np.radians(appearance.limb_azimuth_deg), 90 - appearance.limb_altitude_deg)
    ax.apply_aspect()
    delta = ax.transData.transform(limb) - ax.transData.transform(center)
    image = OffsetImage(phase_disk(appearance.illuminated_fraction, float(np.arctan2(delta[1], delta[0]))), zoom=.08)
    artist = AnnotationBbox(image, center, frameon=False, pad=0, zorder=5)
    ax.add_artist(artist)
    return artist
