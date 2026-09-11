from dataclasses import replace
from unittest.mock import patch
import numpy as np
import pytest
from astropy import units as u
from astropy.time import Time

from neomapper.application.object_summary import calculate_object_summary
from neomapper.domain.object_summary import SummarySample, SummaryTarget, minimum_candidates
from neomapper.infrastructure.ephemeris.summary import HorizonsSummaryProvider


def sample(instant: Time, delta: float = 1.) -> SummarySample:
    return SummarySample(instant, 1.5, delta, 51., 8., 11.3, "T", 115., 31., 260.)


def test_closest_approach_refines_multiple_minima() -> None:
    reference = Time("2026-09-09", scale="utc")
    class Provider:
        def resolve(self, query: str, instant: Time) -> SummaryTarget:
            return SummaryTarget(query, "1", True, reference - 90*u.day)
        def samples(self, target: SummaryTarget, instants: Time) -> list[SummarySample]:
            rows = []
            for instant in instants:
                days = float((instant-reference).to_value(u.day))
                delta = min(1 + (days-33.12345)**2 / 100, 2 + (days+100.5)**2 / 100)
                rows.append(sample(instant, delta))
            return rows
    result = calculate_object_summary("220P", reference, Provider())
    assert abs((result.closest.instant - (reference + 33.12345*u.day)).to_value(u.s)) < 60
    assert result.closest.delta_au == pytest.approx(1., abs=1e-6)
    assert (result.search_stop-result.search_start).to_value(u.day) == pytest.approx(730)
    assert (result.perihelion.instant-reference).to_value(u.day) == pytest.approx(-90)


def test_minimum_candidates_include_boundaries_and_reject_invalid_values() -> None:
    t = Time("2026-09-09", scale="utc")
    assert minimum_candidates([sample(t, x) for x in [1., 2., 1., 2., .5]]) == [0, 2, 4]
    with pytest.raises(ValueError):
        minimum_candidates([sample(t, float("nan"))])


@pytest.mark.parametrize("kind, comet", [("cn", True), ("cu", True), ("an", False), ("au", False)])
def test_provider_uses_authoritative_classification_and_tdb_perihelion(kind: str, comet: bool) -> None:
    instant = Time("2026-09-09", scale="utc")
    with patch("neomapper.infrastructure.ephemeris.summary.requests.get") as get, patch("neomapper.infrastructure.ephemeris.summary.Horizons") as horizons:
        get.return_value.json.return_value = {"object": {"kind": kind, "spkid": "1000498", "fullname": "Fixture"}}
        horizons.return_value.elements.return_value = [{"Tp_jd": 2461205.5}]
        result = HorizonsSummaryProvider().resolve("Fixture", instant)
        assert result.is_comet is comet
        assert result.perihelion.scale == "tdb"
        assert horizons.call_args.kwargs["epochs"] == pytest.approx(instant.tdb.jd)
        assert horizons.call_args.kwargs["id_type"] == (None if comet else "designation")
        if comet:
            assert horizons.call_args.kwargs["id"] == f"DES=1000498;CAP<{instant.tdb.jd:.8f};"
            assert result.horizons_id == horizons.call_args.kwargs["id"]
        assert get.call_args.kwargs["timeout"] == 20


def test_provider_preserves_epoch_order_and_suppresses_asteroid_pa() -> None:
    t = Time("2026-09-09", scale="utc")
    epochs = Time([t.jd+1, t.jd], format="jd", scale="utc")
    rows = [{"datetime_jd": jd, "r": 1.5, "delta": 1., "V": np.ma.masked, "Tmag": 12., "sunTargetPA": 370.} for jd in sorted(epochs.jd)]
    with patch("neomapper.infrastructure.ephemeris.summary.Horizons") as horizons:
        horizons.return_value.ephemerides.return_value = rows
        target = SummaryTarget("Fixture", "1", True, t)
        provider = HorizonsSummaryProvider()
        comet = provider.samples(target, epochs)
        assert comet[0].instant.jd == pytest.approx(epochs[0].jd)
        assert comet[0].tail_pa_deg == pytest.approx(10.)
        assert comet[0].magnitude == pytest.approx(12.)
        asteroid = provider.samples(replace(target, is_comet=False), epochs)
        assert asteroid[0].tail_pa_deg is None
        assert horizons.call_args.kwargs["location"] == "500@399"
