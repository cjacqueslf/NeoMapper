import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from astropy.time import Time

from neomapper.domain.observing import (
    make_grid,
    max_altitude_point,
    observational_window_and_best,
)


class ObservingGridTests(unittest.TestCase):
    def test_grid_has_matching_shapes_and_global_extent(self):
        longitude, latitude = make_grid(90.0)
        self.assertEqual(longitude.shape, latitude.shape)
        self.assertEqual(float(longitude.min()), -180.0)
        self.assertEqual(float(longitude.max()), 180.0)
        self.assertLessEqual(float(latitude.min()), -89.5)
        self.assertGreaterEqual(float(latitude.max()), 89.5)

    def test_maximum_altitude_returns_corresponding_coordinates(self):
        altitude = np.array([[1.0, 2.0], [9.0, 3.0]])
        longitude = np.array([[-10.0, 10.0], [-10.0, 10.0]])
        latitude = np.array([[-20.0, -20.0], [20.0, 20.0]])
        self.assertEqual(max_altitude_point(altitude, longitude, latitude), (20.0, -10.0, 9.0))

    def test_observational_window_does_not_span_ineligible_gap(self):
        ephemerides = [
            SimpleNamespace(jd=Time(value, scale="utc").jd)
            for value in (
                "2029-04-13 20:00:00",
                "2029-04-13 21:00:00",
                "2029-04-13 22:00:00",
                "2029-04-13 23:00:00",
                "2029-04-14 00:00:00",
            )
        ]
        samples = iter([
            (20.0, 0.0, -20.0),
            (30.0, 0.0, -20.0),
            (-5.0, 0.0, -20.0),
            (40.0, 0.0, -20.0),
            (35.0, 0.0, -20.0),
        ])

        with patch("neomapper.domain.observing.altitude_at_reference_site", side_effect=samples):
            result = observational_window_and_best(ephemerides, -19.9, -43.9)

        self.assertEqual(result["window_start"].utc.iso[11:16], "23:00")
        self.assertEqual(result["window_stop"].utc.iso[11:16], "00:00")
        self.assertEqual(result["best"].altitude_deg, 40.0)
