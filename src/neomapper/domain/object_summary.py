"""Scientific values for the three-row orbital summary."""
from __future__ import annotations

from dataclasses import dataclass
import math
from astropy.time import Time


@dataclass(frozen=True)
class SummaryTarget:
    name: str
    spk_id: str
    is_comet: bool
    perihelion: Time
    period_days: float | None = None
    horizons_id: str | None = None


@dataclass(frozen=True)
class SummarySample:
    instant: Time
    radius_au: float
    delta_au: float
    ra_deg: float | None
    dec_deg: float | None
    magnitude: float | None
    magnitude_band: str
    elongation_deg: float | None
    phase_deg: float | None
    tail_pa_deg: float | None


@dataclass(frozen=True)
class ObjectSummary:
    target: SummaryTarget
    perihelion: SummarySample
    selected: SummarySample
    closest: SummarySample
    search_start: Time
    search_stop: Time
    extended_search: bool = False
    perihelion_refined: bool = False
    search_limited: bool = False


def minimum_candidates(samples: list[SummarySample]) -> list[int]:
    """Daily local minima plus boundaries, ordered in time; no global extrapolation."""
    if not samples or any(not math.isfinite(row.delta_au) or row.delta_au <= 0 for row in samples):
        raise ValueError("Invalid distance samples")
    return sorted({0, len(samples) - 1, *(
        i for i in range(1, len(samples) - 1)
        if samples[i].delta_au < samples[i-1].delta_au and samples[i].delta_au <= samples[i+1].delta_au
    )})
