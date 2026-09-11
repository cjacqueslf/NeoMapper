import unittest

import numpy as np
from astropy.time import Time
from astropy.utils import iers

from neomapper.domain.observing import moon_altitudes_deg


class MoonAltitudeTests(unittest.TestCase):
    def test_builtin_topocentric_altitude_regression(self) -> None:
        # Astropy builtin lunar ephemeris, airless, 850 m, UTC. A 0.001 degree
        # tolerance allows small bundled IERS changes, while guarding frame,
        # observer, and time regressions. This is not an external accuracy claim.
        times = Time(["2025-01-15 00:00", "2025-01-15 06:00", "2025-01-15 12:00"], scale="utc")
        with iers.conf.set_temp("auto_download", False):
            result = moon_altitudes_deg(times, -19.9, -43.9, 850)
            wrapped = moon_altitudes_deg(times, -19.9, 316.1, 850)
        np.testing.assert_allclose(result, [16.33635697, 41.13727274, -28.31878125], atol=.001, rtol=0)
        np.testing.assert_allclose(result, wrapped, atol=1e-8, rtol=0)
