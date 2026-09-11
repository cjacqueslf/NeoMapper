import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation
from astropy.time import Time

from neomapper.domain.lunar_phase import lunar_appearance
from neomapper.presentation.lunar_marker import phase_disk
from neomapper.presentation.skymap import _solar_system_positions


@pytest.mark.parametrize("sun_az, expected", [(0, 0), (90, .5), (180, 1), (270, .5)])
def test_phase_geometry(sun_az: float, expected: float) -> None:
    phase = lunar_appearance(0, 0, .00257, sun_az, 0, 1)
    assert phase.illuminated_fraction == pytest.approx(expected, abs=.002)


@pytest.mark.parametrize("instant, expected", [
    ("2026-09-11T03:27:00", 0), ("2026-09-18T20:44:00", .5),
    ("2026-09-26T16:49:00", 1), ("2026-10-03T13:25:00", .5),
])
def test_known_phases_from_usno(instant: str, expected: float) -> None:
    # USNO primary phases, UT: https://aa.usno.navy.mil/calculated/moon/phases?date=2026-09-01&nump=8
    # 0.02 tolerates topocentric parallax and builtin ephemeris differences.
    t = Time(instant, scale="utc")
    location = EarthLocation(lat=-19.9*u.deg, lon=-43.9*u.deg, height=850*u.m)
    bodies = _solar_system_positions(t, location, AltAz(obstime=t, location=location, pressure=0*u.hPa))
    moon, sun = bodies["moon"], bodies["sun"]
    phase = lunar_appearance(moon["az"], moon["alt"], moon["distance_au"], sun["az"], sun["alt"], sun["distance_au"])
    assert phase.illuminated_fraction == pytest.approx(expected, abs=.02)


@pytest.mark.parametrize("fraction", [0, .1, .5, .9, 1])
def test_disk_illuminated_area_matches_phase(fraction: float) -> None:
    pixels = phase_disk(fraction, 0)
    inside = pixels[:, :, 3] > 0
    bright = pixels[:, :, 0] > .5
    assert bright[inside].mean() == pytest.approx(fraction, abs=.012)


def test_rotating_limb_reverses_bright_side() -> None:
    right = phase_disk(.5, 0)
    left = phase_disk(.5, np.pi)
    assert right[:, 80, 0].mean() > left[:, 80, 0].mean()
