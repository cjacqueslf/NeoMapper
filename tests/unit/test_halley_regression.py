import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from astropy import units as u
from astropy.time import Time

from neomapper.application.solar_system import object_orbit
from neomapper.application.object_summary import calculate_object_summary
from neomapper.domain.object_summary import SummarySample, SummaryTarget
from neomapper.infrastructure.ephemeris.solar_system import load_object_orbit
from neomapper.infrastructure.ephemeris.summary import HorizonsSummaryProvider


def test_horizons_state_uses_same_apparition_tdb_and_geometric_frame() -> None:
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/halley_2026.json").read_text())
    instant = Time(fixture["epoch_utc"], scale="utc")
    target = SummaryTarget("1P/Halley", "1000036", True, instant, 27567., fixture["command"])
    with patch("neomapper.infrastructure.ephemeris.solar_system.HorizonsSummaryProvider.resolve", return_value=target), patch("neomapper.infrastructure.ephemeris.solar_system.Horizons") as horizons:
        horizons.return_value.vectors.return_value = [dict(zip(("x", "y", "z", "vx", "vy", "vz"), fixture["position_au"] + fixture["velocity_au_day"]))]
        orbit = load_object_orbit("1P", instant)
        assert horizons.call_args.kwargs["id"] == fixture["command"]
        assert horizons.call_args.kwargs["epochs"] == pytest.approx(instant.tdb.jd, abs=1e-9, rel=0)
        horizons.return_value.vectors.assert_called_once_with(refplane="ecliptic", aberrations="geometric")
        np.testing.assert_allclose(orbit.position_au, fixture["position_au"])
    future = Time([instant.jd+12000], format="jd", scale="utc")
    with patch("neomapper.infrastructure.ephemeris.summary.Horizons") as horizons:
        horizons.return_value.ephemerides.return_value = [{"datetime_jd": future[0].jd, "r": .6, "delta": .5}]
        HorizonsSummaryProvider().samples(target, future)
        assert horizons.call_args.kwargs["id"] == fixture["command"]
        assert horizons.call_args.kwargs["id_type"] is None


def test_halley_inclined_retrograde_orbit_matches_marker() -> None:
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/halley_2026.json").read_text())
    orbit = object_orbit("1P/Halley", fixture["position_au"], fixture["velocity_au_day"])
    assert orbit.semi_major_au == pytest.approx(fixture["elements"]["a"], rel=1e-7)
    assert orbit.eccentricity == pytest.approx(fixture["elements"]["e"], rel=1e-7)
    assert np.linalg.norm(orbit.position_au) > orbit.semi_major_au
    np.testing.assert_allclose(orbit.path_au[0], orbit.position_au, atol=1e-10)
    np.testing.assert_allclose(orbit.path_au[-1], orbit.position_au, atol=1e-10)
    normal = np.cross(fixture["position_au"], fixture["velocity_au_day"])
    assert normal[2] < 0
    np.testing.assert_allclose(orbit.path_au @ normal, 0, atol=1e-10)


@pytest.mark.parametrize("period,eccentricity,expected", [(27567., .968, 27567.), (0., .5, None), (1000., 1.1, None), (float("nan"), .5, None)])
def test_period_extension_requires_valid_bound_orbit(period: float, eccentricity: float, expected: float | None) -> None:
    instant = Time("2026-09-10", scale="utc")
    with patch("neomapper.infrastructure.ephemeris.summary.requests.get") as get, patch("neomapper.infrastructure.ephemeris.summary.Horizons") as horizons:
        get.return_value.json.return_value = {"object": {"kind": "cn", "des": "1P", "spkid": "1000036", "fullname": "1P/Halley"}}
        horizons.return_value.elements.return_value = [{"Tp_jd": 2474040.98, "P": period, "e": eccentricity}]
        target = HorizonsSummaryProvider().resolve("1P", instant)
        assert target.period_days == expected
        assert target.horizons_id.startswith("DES=1P;CAP<")


@pytest.mark.parametrize("past", [False, True])
def test_long_period_search_refines_next_return(past: bool) -> None:
    reference = Time("2026-09-10", scale="utc")
    seed = reference.tdb + 12000*u.day
    class Provider:
        def resolve(self, query: str, instant: Time) -> SummaryTarget:
            return SummaryTarget(query, "1", True, seed - (27500 if past else 0)*u.day, 27500)
        def samples(self, target: SummaryTarget, instants: Time) -> list[SummarySample]:
            return [SummarySample(t, .6 + ((t-seed).to_value(u.day)-20.123)**2/10000,
                                  .5 + ((t-seed).to_value(u.day)+40.345)**2/10000,
                                  None, None, None, "", None, None, None) for t in instants]
    result = calculate_object_summary("1P", reference, Provider())
    assert result.extended_search and result.perihelion_refined
    assert not result.search_limited
    assert abs((result.perihelion.instant-seed).to_value(u.day)-20.123) < 1/1440
    assert abs((result.closest.instant-seed).to_value(u.day)+40.345) < 1/1440
    assert abs((result.selected.instant-reference).to_value(u.s)) < .001
    assert (result.search_start-seed).to_value(u.day) == pytest.approx(-365)


def test_edge_minimum_is_reported_as_estimated_perihelion() -> None:
    reference = Time("2026-09-10", scale="utc")
    seed = reference + 2000*u.day
    class Provider:
        def resolve(self, query: str, instant: Time) -> SummaryTarget:
            return SummaryTarget(query, "1", True, seed, 5000)
        def samples(self, target: SummaryTarget, instants: Time) -> list[SummarySample]:
            return [SummarySample(t, 100+(t-reference).to_value(u.day)/100, 1.,
                                  None, None, None, "", None, None, None) for t in instants]
    result = calculate_object_summary("x", reference, Provider())
    assert result.extended_search and result.search_limited
    assert not result.perihelion_refined
    assert abs((result.perihelion.instant-seed).to_value(u.s)) < .001


@pytest.mark.parametrize("period", [None, 27500])
def test_nearby_perihelion_keeps_standard_window(period: float | None) -> None:
    reference = Time("2026-09-10", scale="utc")
    class Provider:
        def resolve(self, query: str, instant: Time) -> SummaryTarget:
            return SummaryTarget(query, "1", True, reference+10*u.day, period)
        def samples(self, target: SummaryTarget, instants: Time) -> list[SummarySample]:
            return [SummarySample(t, 1., 1.+((t-reference).to_value(u.day)/100)**2,
                                  None, None, None, "", None, None, None) for t in instants]
    result = calculate_object_summary("x", reference, Provider())
    assert not result.extended_search
    assert (result.search_start-reference).to_value(u.day) == pytest.approx(-365)
