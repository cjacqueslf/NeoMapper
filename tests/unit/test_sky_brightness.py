import unittest
from contextlib import ExitStack
from unittest.mock import patch
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.text import Text
from neomapper.domain.sky_brightness import star_visibility, target_visibility, milky_way_visibility, twilight_magnitude_limit
from neomapper.presentation.sky_visibility import target_status
from neomapper.application.ephemerides import Ephemeris
from neomapper.presentation import skymap, skymap_observing


class SkyBrightnessTests(unittest.TestCase):
    def test_day_hides_even_bright_stars_and_milky_way(self):
        np.testing.assert_array_equal(star_visibility([-2., 0., 6.], [60.,60.,60.], 0.), 0.)
        self.assertEqual(milky_way_visibility(-12.), 0.)
        self.assertEqual(milky_way_visibility(-18.), 1.)

    def test_dusk_gradually_reveals_stars_and_respects_user_limit(self):
        sun = np.linspace(0., -18., 181)
        for magnitude in (-1., 1., 3., 5., 6.9):
            opacity = [float(star_visibility(magnitude, 90., alt)) for alt in sun]
            self.assertTrue(np.all(np.diff(opacity) >= -1e-12))
            self.assertTrue(any(0 < value < 1 for value in opacity))
            self.assertEqual(opacity[-1], 1.)
        self.assertGreater(star_visibility(-1.,60.,-6.), star_visibility(3.,60.,-6.))
        self.assertEqual(star_visibility(5.,90.,-20.,4.), 0.)
        self.assertEqual(star_visibility(-1.,-1.,-20.), 0.)
        for boundary in (-6., -12., -18.):
            self.assertAlmostEqual(twilight_magnitude_limit(boundary-1e-7), twilight_magnitude_limit(boundary+1e-7), places=5)

    def test_target_reason_does_not_confuse_horizon_glare_or_unknown_magnitude(self):
        self.assertEqual(target_visibility(20.,45.,-1.), "sky_glare")
        self.assertEqual(target_visibility(-6.,45.,10.), "sky_glare")
        self.assertEqual(target_visibility(-6.,45.,0.), "above_horizon")
        self.assertEqual(target_visibility(20.,-5.,10.), "below_horizon")
        self.assertEqual(target_visibility(-6.,45.,None), "unknown_twilight")
        self.assertEqual(target_visibility(-20.,45.,15.), "above_horizon")
        for language, phrase in [("PT","Ofuscado"),("EN","Obscured"),("ES","Ofuscado")]:
            self.assertIn(phrase,target_status(20.,45.,10.,language))

    def test_daytime_render_hides_stars_planets_and_keeps_target_and_moon(self):
        eph=Ephemeris("Fixture", "2026-09-08 15:00:00", 180.,-20.,0.,45.,1.,149597870.7,vmag=12.)
        for module in (skymap,skymap_observing):
            positions={key:{"label":label,"color":color,"size":size,"marker":marker,"alt":45.,"az":50.+i*20} for i,(key,(label,color,size,marker)) in enumerate(module.SOLAR_SYSTEM_BODIES.items())}
            for key, body in positions.items():
                body["distance_au"] = .00257 if key == "moon" else 1.
            with self.subTest(renderer=module.__name__), ExitStack() as stack:
                stack.enter_context(patch.object(module,"query_horizons",return_value=eph))
                stack.enter_context(patch.object(module,"_solar_system_positions",return_value=positions))
                if hasattr(module,"query_horizons_range"):
                    stack.enter_context(patch.object(module,"query_horizons_range",return_value=[]))
                fig,result=module.build_sky_figure("Fixture","2026-09-08 15:00:00",language="PT")
                try:
                    texts=[t.get_text() for t in fig.findobj(match=Text)]
                    self.assertIn("Sol",texts)
                    self.assertIn("Lua",texts)
                    self.assertNotIn("Júpiter",texts)
                    self.assertNotIn("Sirius",texts)
                    for collection in fig.axes[0].collections:
                        if collection.get_zorder() in (1.1,1.3,3.7,4):
                            self.assertEqual(len(collection.get_offsets()),0)
                    if result["current_altitude"]>=0:
                        self.assertIn("Ofuscado", " ".join(texts))
                    fig.canvas.draw()
                finally:
                    plt.close(fig)
