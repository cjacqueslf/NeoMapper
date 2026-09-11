from unittest.mock import patch
import pytest
from astropy.time import Time
from neomapper.application.ephemerides import query_report_ephemerides


def test_report_preserves_native_observer_rates_and_utc() -> None:
    row = dict(targetname="220P", datetime_jd=2461292.5, RA=51.0, DEC=8.0,
               AZ=87.8, EL=-19.4, Sky_motion=0.535, Sky_mot_PA=113.2, Tmag=14.95)
    with patch("neomapper.application.ephemerides.Horizons") as provider:
        provider.return_value.ephemerides.return_value = [row]
        rows = query_report_ephemerides("220P", Time("2026-09-09", scale="utc"),
                                       Time("2026-09-10", scale="utc"), "1h", -19.9, 316.1)
        assert provider.call_args.kwargs["location"]["lon"] == pytest.approx(-43.9)
        assert rows[0]["Sky_motion"] == pytest.approx(.535)
        assert rows[0]["Sky_mot_PA"] == pytest.approx(113.2)
        assert rows[0]["EL"] == pytest.approx(-19.4)
        assert rows[0]["V"] is None
        assert rows[0]["Tmag"] == pytest.approx(14.95)


def test_report_rejects_reversed_interval_before_network() -> None:
    with patch("neomapper.application.ephemerides.Horizons") as provider:
        with pytest.raises(ValueError):
            query_report_ephemerides("220P", Time("2026-09-10", scale="utc"),
                                    Time("2026-09-09", scale="utc"), "1h", 0, 0)
        provider.assert_not_called()
