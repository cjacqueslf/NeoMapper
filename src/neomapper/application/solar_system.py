"""Heliocentric planetary states and osculating paths for the solar plot."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from astropy import units as u
from astropy.constants import GM_sun
from astropy.coordinates import (
    BarycentricMeanEcliptic, CartesianDifferential, SkyCoord,
    get_body_barycentric_posvel,
)
from astropy.time import Time

from neomapper.domain.orbits import osculating_orbit


@dataclass(frozen=True)
class ObjectOrbit:
    name: str
    position_au: np.ndarray
    path_au: np.ndarray
    semi_major_au: float
    eccentricity: float


def object_orbit(name: str, position_au: np.ndarray, velocity_au_day: np.ndarray) -> ObjectOrbit:
    """Projectable osculating ellipse from one geometric ecliptic J2000 state."""
    r = np.asarray(position_au, dtype=float)
    v = np.asarray(velocity_au_day, dtype=float)
    mu = GM_sun.to_value(u.au ** 3 / u.day ** 2)
    path = osculating_orbit(r, v, mu)
    radius = np.linalg.norm(r)
    a = 1 / (2 / radius - np.dot(v, v) / mu)
    e = np.linalg.norm(np.cross(v, np.cross(r, v)) / mu - r / radius)
    return ObjectOrbit(name, r, path, float(a), float(e))


def planet_orbit(body: str, instant: Time) -> tuple[np.ndarray, np.ndarray]:
    """Return position and path in heliocentric mean ecliptic J2000 AU.

    Both use the same state, frame and epoch. Solar two-body ellipses are
    instantaneous approximations; planetary perturbations are not propagated.
    """
    position, velocity = get_body_barycentric_posvel(body, instant)
    sun_position, sun_velocity = get_body_barycentric_posvel("sun", instant)
    state = (position - sun_position).with_differentials(
        CartesianDifferential((velocity - sun_velocity).xyz)
    )
    ecliptic = SkyCoord(state, frame="icrs").transform_to(
        BarycentricMeanEcliptic(equinox=Time("J2000", scale="tt"))
    ).cartesian
    r = ecliptic.xyz.to_value(u.au)
    v = ecliptic.differentials["s"].d_xyz.to_value(u.au / u.day)
    path = osculating_orbit(r, v, GM_sun.to_value(u.au ** 3 / u.day ** 2))
    return r, path
