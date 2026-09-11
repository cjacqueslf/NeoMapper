import unittest

from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation
from astropy.time import Time

from neomapper.presentation.skyplot import (
    celestial_trail_to_horizontal,
    visible_target_path,
)


class VisibleTargetPathTests(unittest.TestCase):
    def test_target_below_horizon_is_not_added_to_plot(self):
        path = visible_target_path(123.0, -4.5, [(100.0, 5.0), (110.0, -1.0)])

        self.assertEqual(path, [(100.0, 5.0)])

    def test_target_on_or_above_horizon_is_added_to_plot(self):
        self.assertEqual(visible_target_path(123.0, 0.0, None), [(123.0, 0.0)])
        self.assertEqual(visible_target_path(124.0, 12.5, []), [(124.0, 12.5)])

    def test_celestial_trail_moves_with_sky_between_frames(self):
        location = EarthLocation(lat=-19.9 * u.deg, lon=-43.9 * u.deg)
        first_frame = AltAz(
            obstime=Time("2029-04-13 22:00:00", scale="utc"),
            location=location,
        )
        later_frame = AltAz(
            obstime=Time("2029-04-13 23:00:00", scale="utc"),
            location=location,
        )

        first = celestial_trail_to_horizontal([(120.0, -15.0)], first_frame)[0]
        later = celestial_trail_to_horizontal([(120.0, -15.0)], later_frame)[0]

        self.assertNotAlmostEqual(first[0], later[0], places=3)
        self.assertNotAlmostEqual(first[1], later[1], places=3)


if __name__ == "__main__":
    unittest.main()
