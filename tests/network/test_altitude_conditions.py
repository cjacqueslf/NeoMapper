import pytest
from astropy.time import Time
from neomapper.presentation.altitude_plot import build_altitude_chart


@pytest.mark.network
def test_rw3_night_matches_observing_panel(tmp_path) -> None:
    result = build_altitude_chart("2026 RW3", Time("2026-09-09T21:42:00", scale="utc"),
                                  -19.9, -43.9, 850, tmp_path / "rw3.png", time_mode="LOCAL", return_details=True)
    best = result.observation["best"]
    assert best.altitude_deg == pytest.approx(89.7, abs=.2)
    assert abs((best.time - Time("2026-09-10T00:25:00", scale="utc")).to_value("sec")) < 300
