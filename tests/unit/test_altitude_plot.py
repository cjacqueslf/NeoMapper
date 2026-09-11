import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from astropy.time import Time
import numpy as np
from neomapper.presentation.altitude_plot import build_altitude_chart, twilight_spans, AltitudeChartResult


class AltitudeChartTests(unittest.TestCase):
    def test_twilight_spans_cover_every_interval_without_gaps(self) -> None:
        spans = twilight_spans(np.array([10, -22, -22, 10]))
        self.assertAlmostEqual(spans[0][0], 0)
        self.assertAlmostEqual(spans[-1][1], 3)
        for previous, following in zip(spans[:-1], spans[1:]):
            self.assertAlmostEqual(previous[1], following[0])
        self.assertEqual([span[2] for span in spans], [0, 1, 2, 3, 4, 3, 2, 1, 0])
        self.assertAlmostEqual(spans[0][1], 10 / 32)

    def test_chart_uses_utc_envelope_and_observer_height(self) -> None:
        rows = [SimpleNamespace(jd=Time(f"2026-09-07 {hour}:00:00", scale="utc").jd,
                                source="fixture", target_name="Test") for hour in (12, 15, 18)]
        with tempfile.TemporaryDirectory() as folder, patch(
            "neomapper.presentation.altitude_plot.query_horizons_range", return_value=rows,
        ) as query, patch(
            "neomapper.presentation.altitude_plot.altitude_at_reference_site",
            side_effect=[(-5, 0, 30), (40, 0, -8), (70, 0, -20)],
        ) as altitude:
            path = Path(folder) / "chart.png"
            moon_path = Path(folder) / "chart_moon.png"
            with patch("neomapper.presentation.altitude_plot.moon_altitudes_deg",
                       return_value=np.array([20, 45, 10])) as moon:
                build_altitude_chart("99942", Time("2026-09-07 20:00", scale="utc"),
                                     -20, 360, 850, path, "PT", moon_output_png=moon_path)
                self.assertEqual(moon.call_args.args[0].scale, "utc")
                self.assertEqual(moon.call_args.args[1:], (-20, 0, 850))
            self.assertGreater(moon_path.stat().st_size, 1000)
            self.assertNotEqual(path.read_bytes(), moon_path.read_bytes())
            self.assertGreater(path.stat().st_size, 1000)
            _, start, stop = query.call_args.args
            self.assertEqual(start.scale, "utc")
            self.assertAlmostEqual((stop - start).to_value("hour"), 24)
            self.assertEqual(query.call_args.kwargs["step"], "5m")
            self.assertEqual(altitude.call_args.args[2:], (-20, 0, 850))

    def test_empty_provider_result_is_an_error(self) -> None:
        with patch("neomapper.presentation.altitude_plot.query_horizons_range", return_value=[]):
            with self.assertRaisesRegex(ValueError, "Insufficient"):
                build_altitude_chart("test", Time("2026-09-07", scale="utc"), 0, 0, 0, Path("unused.png"))

    def test_chart_best_uses_observing_constraints_not_unrestricted_maximum(self) -> None:
        rows = [SimpleNamespace(jd=Time(f"2026-09-09 {hour}:00:00", scale="utc").jd,
                                source="fixture", target_name="Test") for hour in (18, 19, 20)]
        with tempfile.TemporaryDirectory() as folder, patch(
            "neomapper.presentation.altitude_plot.query_horizons_range", return_value=rows
        ), patch("neomapper.presentation.altitude_plot.altitude_at_reference_site",
                 side_effect=[(89., 0., 10.), (70., 0., -15.), (50., 0., -20.)]):
            result = build_altitude_chart("Test", Time("2026-09-09T21:42:00", scale="utc"),
                                         -19.9, -43.9, 850, Path(folder)/"chart.png",
                                         min_altitude_deg=60, sun_limit_deg=-12, return_details=True)
            self.assertIsInstance(result, AltitudeChartResult)
            self.assertAlmostEqual(result.observation["best"].altitude_deg, 70.)
            self.assertEqual(result.observation["best"].time.utc.iso, "2026-09-09 19:00:00.000")
            self.assertEqual(result.observation["window_start"].utc.iso, result.observation["window_stop"].utc.iso)
