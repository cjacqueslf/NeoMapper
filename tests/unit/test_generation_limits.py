from pathlib import Path
from unittest.mock import patch

import pytest
from astropy.time import Time
from neomapper.application.generation_limits import GenerationLimitError, sample_count
from neomapper.application.ephemerides import query_report_ephemerides
from neomapper.presentation.animation import generate_animation


@pytest.mark.parametrize("duration, step, endpoint, expected", [
    (499*60, 60, True, 500), (500*60, 60, True, 501),
    (499*60+1, 60, True, 501), (499*60+1, 60, False, 500),
    (60, 120, True, 2), (60, 120, False, 1),
])
def test_sample_counts(duration: float, step: float, endpoint: bool, expected: int) -> None:
    assert sample_count(duration, step, include_end=endpoint) == expected


def test_animation_rejects_before_creating_frames(tmp_path: Path) -> None:
    with patch("neomapper.presentation.animation.build_visibility_figure") as render:
        with pytest.raises(ValueError, match="501.*500"):
            generate_animation(object_query="Fixture", start_time="2026-09-09 00:00:00",
                               end_time="2026-09-09 08:20:00", step_minutes=1,
                               fps=1, export_gif=False, export_mp4=False, base_output=str(tmp_path / "animation"))
        render.assert_not_called()
        assert not list(tmp_path.iterdir())


def test_animation_accepts_custom_limit_and_preserves_endpoint(tmp_path: Path) -> None:
    with patch("neomapper.presentation.animation.build_visibility_figure", return_value=(None, {})) as render:
        generate_animation(object_query="Fixture", start_time="2026-09-09 00:00:00",
                           end_time="2026-09-09 00:10:30", step_minutes=5, max_frames=4,
                           fps=1, export_gif=False, export_mp4=False, base_output=str(tmp_path / "animation"))
        assert render.call_count == 4
        assert render.call_args.kwargs["utc_text"] == "2026-09-09 00:10:30"


def test_report_rejects_before_network_and_accepts_custom_limit() -> None:
    start = Time("2026-09-09T00:00:00", scale="utc")
    stop = Time("2026-09-09T08:20:00", scale="utc")
    with patch("neomapper.application.ephemerides.Horizons") as provider:
        with pytest.raises(GenerationLimitError):
            query_report_ephemerides("Fixture", start, stop, "1m", 0, 0)
        provider.assert_not_called()
        provider.return_value.ephemerides.return_value = []
        query_report_ephemerides("Fixture", start, stop, "1m", 0, 0, max_rows=501)
        provider.assert_called_once()


def test_report_checks_actual_provider_row_count() -> None:
    with patch("neomapper.application.ephemerides.Horizons") as provider:
        provider.return_value.ephemerides.return_value = [{}, {}, {}]
        with pytest.raises(GenerationLimitError):
            query_report_ephemerides("Fixture", Time("2026-09-09", scale="utc"),
                                    Time("2026-09-10", scale="utc"), "1d", 0, 0, max_rows=2)
