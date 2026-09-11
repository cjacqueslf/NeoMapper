"""Calendar animation steps anchored to the requested civil start date."""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from neomapper.application.generation_limits import enforce_limit


def calendar_frames(start: datetime, end: datetime, unit: str, limit: int) -> list[datetime]:
    """Include endpoints; clamp missing month days without cumulative drift."""
    if unit not in ("month", "year") or end <= start:
        raise ValueError("Invalid calendar interval")
    stride = 1 if unit == "month" else 12

    def advance(index: int) -> datetime:
        months = start.year * 12 + start.month - 1 + index * stride
        year, month0 = divmod(months, 12)
        day = min(start.day, monthrange(year, month0 + 1)[1])
        return start.replace(year=year, month=month0 + 1, day=day)

    steps = ((end.year - start.year) * 12 + end.month - start.month) // stride
    if advance(steps) > end:
        steps -= 1
    append_end = advance(steps) < end
    enforce_limit(steps + 1 + int(append_end), limit)
    frames = [advance(index) for index in range(steps + 1)]
    if append_end:
        frames.append(end)
    return frames
