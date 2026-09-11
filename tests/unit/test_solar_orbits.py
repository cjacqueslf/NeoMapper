import unittest
import numpy as np
from astropy.time import Time
from astropy import units as u
from astropy.coordinates import get_body_barycentric
from neomapper.domain.orbits import osculating_orbit
from neomapper.application.solar_system import planet_orbit


class SolarOrbitTests(unittest.TestCase):
    def test_inclined_ellipse_has_correct_apsides_focus_and_plane(self):
        # a=2, e=0.5, mu=1; perihelion=1, aphelion=3, inclined 60 degrees.
        r = np.array([1., 0., 0.])
        direction = np.array([0., .5, np.sqrt(3)/2])
        v = np.sqrt(1.5) * direction
        path = osculating_orbit(r, v, 1.)
        np.testing.assert_allclose(path[0], r, atol=1e-12)
        np.testing.assert_allclose(path[-1], r, atol=1e-12)
        distances = np.linalg.norm(path, axis=1)
        self.assertAlmostEqual(distances.min(), 1.)
        self.assertAlmostEqual(distances.max(), 3.)
        second_focus = np.array([-2., 0., 0.])
        np.testing.assert_allclose(distances + np.linalg.norm(path-second_focus, axis=1), 4., atol=1e-12)
        np.testing.assert_allclose(path @ np.cross(r, v), 0., atol=1e-12)

    def test_circular_orbit_and_unbound_rejection(self):
        path = osculating_orbit(np.array([1.,0.,0.]), np.array([0.,1.,0.]), 1.)
        np.testing.assert_allclose(np.linalg.norm(path, axis=1), 1., atol=1e-12)
        with self.assertRaises(ValueError):
            osculating_orbit(np.array([1.,0.,0.]), np.array([0.,2.,0.]), 1.)

    def test_planets_lie_on_paths_at_selected_epoch(self):
        for date in ("2026-09-08", "2029-04-13"):
            t = Time(date, scale="utc")
            for body in ("mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"):
                with self.subTest(date=date, body=body):
                    position, path = planet_orbit(body, t)
                    np.testing.assert_allclose(path[0], position, atol=1e-10)
                    np.testing.assert_allclose(path[-1], position, atol=1e-10)
                    source = get_body_barycentric(body, t) - get_body_barycentric("sun", t)
                    self.assertAlmostEqual(np.linalg.norm(position), source.norm().to_value(u.au), places=10)
                    self.assertTrue(np.isfinite(path).all())
                    if body == "earth":
                        self.assertLess(abs(position[2]), .001)
