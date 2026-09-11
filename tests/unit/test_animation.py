import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neomapper.presentation.animation import generate_animation


class AnimationOutputTests(unittest.TestCase):
    def test_distance_unit_reaches_every_animation_frame(self):
        for map_type, renderer in (("Sky Map", "build_sky_figure"), ("Visibility Map", "build_visibility_figure")):
            with tempfile.TemporaryDirectory() as folder, patch(
                "neomapper.presentation.animation." + renderer,
                return_value=(None, {"current_altitude": 45., "current_azimuth": 120.}),
            ) as build:
                generate_animation(object_query="Fixture", start_time="2026-09-08 22:00:00",
                    end_time="2026-09-08 22:05:00", base_output=str(Path(folder)/"anim"),
                    step_minutes=5, fps=1, export_gif=False, export_mp4=False, keep_frames=False,
                    map_type=map_type, distance_unit="UA")
                self.assertEqual(build.call_count, 2)
                self.assertTrue(all(call.kwargs["distance_unit"] == "UA" for call in build.call_args_list))

    def test_removes_frame_directory_when_keep_frames_is_disabled(self):
        result_payload = {"zen_lon": 0.0, "zen_lat": 0.0}
        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "sample"
            with patch(
                "neomapper.presentation.animation.build_visibility_figure",
                return_value=(None, result_payload),
            ):
                result = generate_animation(
                    object_query="99942",
                    start_time="2029-04-13 22:00:00",
                    end_time="2029-04-13 22:05:00",
                    base_output=str(output),
                    step_minutes=5,
                    fps=1,
                    export_gif=False,
                    export_mp4=False,
                    keep_frames=False,
                )

            self.assertFalse(Path(result["frames_dir"]).exists())

    def test_sky_animation_stops_after_one_continuous_visible_interval(self):
        altitudes = iter([-3.0, 4.0, 8.0, -2.0, 6.0])
        rendered_altitudes = []

        def build_frame(**kwargs):
            frame = Path(kwargs["output_png"])
            frame.touch()
            altitude = next(altitudes)
            rendered_altitudes.append(altitude)
            return None, {"current_azimuth": 120.0, "current_altitude": altitude}

        with tempfile.TemporaryDirectory() as temporary_dir:
            output = Path(temporary_dir) / "sky"
            with patch(
                "neomapper.presentation.animation.build_sky_figure",
                side_effect=build_frame,
            ):
                result = generate_animation(
                    object_query="99942",
                    start_time="2029-04-13 22:00:00",
                    end_time="2029-04-13 22:20:00",
                    base_output=str(output),
                    step_minutes=5,
                    fps=1,
                    export_gif=False,
                    export_mp4=False,
                    keep_frames=True,
                    map_type="Sky Map",
                )

            frames = sorted(Path(result["frames_dir"]).glob("frame_*.png"))
            self.assertEqual([frame.name for frame in frames], ["frame_0001.png", "frame_0002.png"])
            self.assertEqual(result["frame_count"], 2)
            self.assertEqual(result["effective_start_time"], "2029-04-13 22:05:00")
            self.assertEqual(result["effective_end_time"], "2029-04-13 22:10:00")
            self.assertEqual(rendered_altitudes, [-3.0, 4.0, 8.0, -2.0])

    def test_sky_animation_rejects_interval_entirely_below_horizon(self):
        def build_frame(**kwargs):
            Path(kwargs["output_png"]).touch()
            return None, {"current_azimuth": 120.0, "current_altitude": -3.0}

        with tempfile.TemporaryDirectory() as temporary_dir:
            with patch(
                "neomapper.presentation.animation.build_sky_figure",
                side_effect=build_frame,
            ):
                with self.assertRaisesRegex(ValueError, "abaixo do horizonte"):
                    generate_animation(
                        object_query="99942",
                        start_time="2029-04-13 22:00:00",
                        end_time="2029-04-13 22:05:00",
                        base_output=str(Path(temporary_dir) / "sky"),
                        step_minutes=5,
                        fps=1,
                        export_gif=False,
                        export_mp4=False,
                        map_type="Sky Map",
                        language="PT",
                    )

    def test_sky_trail_passes_equatorial_marks_to_later_frames(self):
        received_trails = []
        samples = iter([
            (100.0, 20.0, 12.0, -4.0),
            (101.0, 21.0, 12.1, -3.9),
        ])

        def build_frame(**kwargs):
            Path(kwargs["output_png"]).touch()
            received_trails.append(list(kwargs["trail_positions"] or []))
            azimuth, altitude, ra, dec = next(samples)
            return None, {
                "current_azimuth": azimuth,
                "current_altitude": altitude,
                "current_ra_deg": ra,
                "current_dec_deg": dec,
            }

        with tempfile.TemporaryDirectory() as temporary_dir:
            with patch(
                "neomapper.presentation.animation.build_sky_figure",
                side_effect=build_frame,
            ):
                generate_animation(
                    object_query="99942",
                    start_time="2029-04-13 22:00:00",
                    end_time="2029-04-13 22:05:00",
                    base_output=str(Path(temporary_dir) / "sky_trail"),
                    step_minutes=5,
                    fps=1,
                    export_gif=False,
                    export_mp4=False,
                    trail_enabled=True,
                    map_type="Sky Map",
                )

        self.assertEqual(received_trails, [[], [(100.0, 20.0, "2029-04-13 22:00:00")]])


if __name__ == "__main__":
    unittest.main()
