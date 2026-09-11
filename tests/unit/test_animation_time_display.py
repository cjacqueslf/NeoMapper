from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import pytest
from neomapper.application.ephemerides import Ephemeris
from neomapper.presentation import mapplot, skymap, skymap_observing
from neomapper.presentation.animation import generate_animation


@pytest.mark.parametrize("module", [mapplot, skymap, skymap_observing])
@pytest.mark.parametrize("mode, expected", [("LOCAL", "2026-09-09 22:00:00"), ("UTC", "2026-09-10 01:00:00")])
def test_title_mode_does_not_change_query_instant(module, mode: str, expected: str) -> None:
    eph = Ephemeris("Fixture", "2026-09-10 01:00:00", 180., -20., 0., 45., 1., 149597870.7, vmag=12.)
    with ExitStack() as stack:
        query = stack.enter_context(patch.object(module, "query_horizons", return_value=eph))
        if hasattr(module, "query_horizons_range"):
            stack.enter_context(patch.object(module, "query_horizons_range", return_value=[]))
        builder = module.build_visibility_figure if module is mapplot else module.build_sky_figure
        fig, result = builder("Fixture", "2026-09-10 01:00:00", time_mode="UTC", display_time_mode=mode,
                              reference_lat=-19.9, reference_lon=-43.9)
        try:
            assert query.call_args.args[1].utc.isot == "2026-09-10T01:00:00.000"
            assert result["display_time"] == expected
            assert result["display_label"] == mode
            titles = " ".join(ax.get_title(loc=loc) for ax in fig.axes for loc in ("left", "center", "right"))
            assert f"{expected} {mode}" in titles
        finally:
            plt.close(fig)


def test_animation_passes_utc_instants_and_local_display(tmp_path: Path) -> None:
    with patch("neomapper.presentation.animation.build_visibility_figure", return_value=(None, {})) as build:
        generate_animation(object_query="Fixture", start_time="2026-09-09 22:00:00",
                           end_time="2026-09-09 22:05:00", time_mode="LOCAL", step_minutes=5,
                           fps=1, export_gif=False, export_mp4=False, base_output=str(tmp_path / "anim"))
        assert build.call_args_list[0].kwargs["utc_text"] == "2026-09-10 01:00:00"
        for call in build.call_args_list:
            assert call.kwargs["time_mode"] == "UTC"
            assert call.kwargs["display_time_mode"] == "LOCAL"
