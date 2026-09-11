"""Build a bounded, geocentric orbital summary through a provider contract."""
from __future__ import annotations

from typing import Protocol
import math
import numpy as np
from astropy import units as u
from astropy.time import Time
from neomapper.domain.object_summary import ObjectSummary, SummarySample, SummaryTarget, minimum_candidates


class SummaryProvider(Protocol):
    def resolve(self, query: str, instant: Time) -> SummaryTarget: ...
    def samples(self, target: SummaryTarget, instants: Time) -> list[SummarySample]: ...


def _checked_samples(provider: SummaryProvider, target: SummaryTarget, times: Time) -> list[SummarySample]:
    rows = provider.samples(target, times)
    if len(rows) != len(times):
        raise ValueError("Incomplete summary ephemerides")
    minimum_candidates(rows)
    if any(not math.isfinite(row.radius_au) or row.radius_au <= 0 for row in rows):
        raise ValueError("Invalid heliocentric distance")
    return rows


def _refined_minimum(provider: SummaryProvider, target: SummaryTarget, coarse: list[SummarySample],
                     field: str = "delta_au") -> SummarySample:
    values = [getattr(row, field) for row in coarse]
    indices = sorted({0, len(coarse)-1, *(i for i in range(1, len(coarse)-1)
        if values[i] < values[i-1] and values[i] <= values[i+1])})
    candidates: list[SummarySample] = []
    for index in indices:
        lower = coarse[max(0, index-1)].instant
        upper = coarse[min(len(coarse)-1, index+1)].instant
        hourly = _checked_samples(provider, target, Time(np.linspace(lower.utc.jd, upper.utc.jd, 49), format="jd", scale="utc"))
        best_index = min(range(len(hourly)), key=lambda i: getattr(hourly[i], field))
        lower = hourly[max(0, best_index-1)].instant
        upper = hourly[min(len(hourly)-1, best_index+1)].instant
        fine = _checked_samples(provider, target, Time(np.linspace(lower.utc.jd, upper.utc.jd, 121), format="jd", scale="utc"))
        candidates.append(min(fine, key=lambda row: getattr(row, field)))
    return min(candidates, key=lambda row: getattr(row, field))


def calculate_object_summary(query: str, instant: Time, provider: SummaryProvider) -> ObjectSummary:
    """Use ±365 days normally, or the next perihelion neighborhood for long periods.

    Outside the normal window, a bound period >730 days seeds the next return.
    Its ±365-day neighborhood (future only) is sampled daily and refined to
    <=1 minute for both solar and Earth distance. No global orbital minimum
    or exact perturbed return time is inferred from the osculating period.
    """
    target = provider.resolve(query, instant)
    start, stop = instant.utc - 365*u.day, instant.utc + 365*u.day
    period = target.period_days
    extended = (period is not None and math.isfinite(period) and period > 730
                and not start <= target.perihelion.utc <= stop)
    if extended:
        seed = target.perihelion.tdb
        if seed <= instant.tdb:
            cycles = math.floor((instant.tdb.jd - seed.jd) / period) + 1
            seed = seed + cycles * period * u.day
        start = max(instant.utc, seed.utc - 365*u.day)
        stop = seed.utc + 365*u.day
    count = math.ceil((stop-start).to_value(u.day)) + 1
    coarse = _checked_samples(provider, target, Time(np.linspace(start.utc.jd, stop.utc.jd, count), format="jd", scale="utc"))
    closest = _refined_minimum(provider, target, coarse)
    if extended:
        perihelion = _refined_minimum(provider, target, coarse, "radius_au")
        # An edge minimum is not evidence of a perihelion within the window.
        limited = min((perihelion.instant-start).to_value(u.day), (stop-perihelion.instant).to_value(u.day)) < 1/1440
        if limited:
            perihelion = _checked_samples(provider, target, Time([seed.utc.jd], format="jd", scale="utc"))[0]
        selected = _checked_samples(provider, target, Time([instant.utc.jd], format="jd", scale="utc"))[0]
        return ObjectSummary(target, perihelion, selected, closest, start, stop, True, not limited, limited)
    events = _checked_samples(provider, target, Time([target.perihelion.utc.jd, instant.utc.jd], format="jd", scale="utc"))
    return ObjectSummary(target, events[0], events[1], closest, start, stop)
