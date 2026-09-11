from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import pytest

from neomapper.application.animation_schedule import calendar_frames
from neomapper.application.generation_limits import GenerationLimitError
from neomapper.presentation.animation import generate_animation


def test_months_clamp_without_drift_and_include_end() -> None:
    frames = calendar_frames(datetime(2028, 1, 31), datetime(2028, 4, 2), "month", 500)
    assert frames == [datetime(2028, 1, 31), datetime(2028, 2, 29), datetime(2028, 3, 31), datetime(2028, 4, 2)]


def test_years_preserve_leap_day_when_available() -> None:
    frames = calendar_frames(datetime(2024, 2, 29), datetime(2028, 2, 29), "year", 5)
    assert frames[1] == datetime(2025, 2, 28)
    assert frames[-1] == datetime(2028, 2, 29)
    with pytest.raises(GenerationLimitError):
        calendar_frames(frames[0], frames[-1], "year", 4)


def test_month_step_reaches_renderer_in_selected_time_mode(tmp_path: Path) -> None:
    with patch("neomapper.presentation.animation.build_visibility_figure", return_value=(None, {})) as build:
        generate_animation(object_query="Fixture", start_time="2026-01-31 22:00:00",
                           end_time="2026-03-31 22:00:00", calendar_step="month", max_frames=3,
                           fps=1, export_gif=False, export_mp4=False, base_output=str(tmp_path / "anim"),
                           time_mode="LOCAL", reference_lat=-19.9, reference_lon=-43.9)
        assert [call.kwargs["utc_text"] for call in build.call_args_list] == [
            "2026-02-01 01:00:00", "2026-03-01 01:00:00", "2026-04-01 01:00:00"]
