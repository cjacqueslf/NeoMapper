import unittest
from contextlib import ExitStack
from unittest.mock import patch
from matplotlib import pyplot as plt
from matplotlib.text import Text
from neomapper.application.ephemerides import Ephemeris
from neomapper.presentation.distances import AU_KM, format_distance, update_figure_distances
from neomapper.presentation import mapplot, skymap, skymap_observing


class DistanceTests(unittest.TestCase):
    def test_exact_au_conversion_localization_and_missing_value(self):
        self.assertEqual(AU_KM, 149597870.7)
        self.assertEqual(format_distance(AU_KM, "UA", "PT"), "1,000000 UA")
        self.assertEqual(format_distance(AU_KM, "UA", "EN"), "1.000000 AU")
        self.assertEqual(format_distance(AU_KM, "km", "PT"), "149.597.871 km")
        self.assertEqual(format_distance(None, "UA", "PT"), "—")
        self.assertNotEqual(format_distance(1., "UA", "EN"), "0.000000 AU")

    def test_solar_title_switches_units_without_changing_orbit(self):
        fig = mapplot.build_solar_system_sketch("Fixture", 1., obstime="2026-09-08", semi_major_au=2., distance_unit="UA", language="PT")
        try:
            ax = fig.axes[0]
            before = ax.lines[0].get_xydata().copy()
            self.assertIn("2,000000 UA", ax.get_title())
            update_figure_distances(fig, "km")
            self.assertIn("299.195.741 km", ax.get_title())
            import numpy as np
            np.testing.assert_array_equal(before, ax.lines[0].get_xydata())
            update_figure_distances(fig, "UA")
            self.assertIn("2,000000 UA", ax.get_title())
        finally:
            plt.close(fig)

    def test_all_map_renderers_use_selected_unit_and_preserve_data(self):
        eph = Ephemeris("Fixture", "2026-09-08 22:00:00", 120., -20., 0., 45., 1., AU_KM, vmag=12.)
        for module in (mapplot, skymap, skymap_observing):
            for unit, expected in (("UA", "1,000000 UA"), ("km", "149.597.871 km")):
                with self.subTest(renderer=module.__name__, unit=unit), ExitStack() as stack:
                    stack.enter_context(patch.object(module, "query_horizons", return_value=eph))
                    if hasattr(module, "query_horizons_range"):
                        stack.enter_context(patch.object(module, "query_horizons_range", return_value=[]))
                    builder = module.build_visibility_figure if module is mapplot else module.build_sky_figure
                    fig, result = builder("Fixture", "2026-09-08 22:00:00", language="PT", distance_unit=unit)
                    try:
                        texts = "\n".join(t.get_text() for t in fig.findobj(match=Text))
                        self.assertIn(expected, texts)
                        self.assertEqual(result["geo_km"], AU_KM)
                    finally:
                        plt.close(fig)
