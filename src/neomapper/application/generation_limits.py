"""Bound generation before allocating samples or contacting a provider."""
from __future__ import annotations

import math
import re
from astropy.time import Time


class GenerationLimitError(ValueError):
    def __init__(self, count: int, limit: int) -> None:
        self.count = count
        self.limit = limit
        super().__init__(f"Requested {count} samples; maximum is {limit}")


def sample_count(duration_seconds: float, step_seconds: float, *, include_end: bool = False) -> int:
    if duration_seconds <= 0 or step_seconds <= 0:
        raise ValueError("Interval and step must be positive")
    quotient = duration_seconds / step_seconds
    nearest = round(quotient)
    if math.isclose(quotient, nearest, rel_tol=0, abs_tol=1e-8):
        quotient = float(nearest)
    return (math.ceil(quotient) if include_end else math.floor(quotient)) + 1


def enforce_limit(count: int, limit: int) -> None:
    if limit < 1:
        raise ValueError("Limit must be positive")
    if count > limit:
        raise GenerationLimitError(count, limit)


def report_sample_count(start: Time, stop: Time, step: str) -> int:
    match = re.fullmatch(r"([1-9][0-9]*)([mhd])", step)
    if not match:
        raise ValueError("Invalid ephemeris step")
    seconds = int(match[1]) * {"m": 60, "h": 3600, "d": 86400}[match[2]]
    return sample_count(float((stop - start).to_value("sec")), seconds)
