import pytest
from astropy.time import Time
from neomapper.application.object_summary import calculate_object_summary
from neomapper.infrastructure.ephemeris.summary import HorizonsSummaryProvider


@pytest.mark.network
def test_live_halley_next_return() -> None:
    summary = calculate_object_summary("1P", Time("2026-09-10", scale="utc"), HorizonsSummaryProvider())
    assert summary.extended_search and summary.perihelion_refined
    assert summary.perihelion.instant.utc.iso.startswith("2061-07-28")
    assert summary.closest.instant.utc.iso.startswith("2061-07-29")
    assert .47 < summary.closest.delta_au < .49


@pytest.mark.network
def test_live_comet_summary() -> None:
    summary = calculate_object_summary("220P", Time("2026-09-09", scale="utc"), HorizonsSummaryProvider())
    assert summary.target.is_comet
    assert summary.selected.tail_pa_deg is not None
    assert summary.perihelion.instant.utc.iso.startswith("2026-06-14")
    assert summary.closest.instant.utc.iso.startswith("2026-10-12")


@pytest.mark.network
def test_live_asteroid_has_no_tail_pa() -> None:
    provider = HorizonsSummaryProvider()
    t = Time("2026-09-09", scale="utc")
    target = provider.resolve("99942", t)
    assert not target.is_comet
    assert provider.samples(target, Time([t.utc.jd], format="jd", scale="utc"))[0].tail_pa_deg is None
