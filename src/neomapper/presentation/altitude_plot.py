"""Night altitude chart using the existing topocentric scientific calculation."""
from __future__ import annotations

from datetime import timezone
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.time import Time
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import DateFormatter, HourLocator
from matplotlib.patches import Patch

from neomapper.application.ephemerides import query_horizons_range
from neomapper.domain.observing import (
    _time_from_ephemeris, altitude_at_reference_site, observing_night_window_utc, moon_altitudes_deg,
    observing_window_from_samples,
)
from neomapper.presentation.i18n import Translator, format_number
from neomapper.shared.utils import timezone_from_reference


@dataclass(frozen=True)
class AltitudeChartResult:
    path: Path
    observation: dict


def twilight_spans(sun_altitudes_deg: np.ndarray) -> list[tuple[float, float, int]]:
    """Cover every sample interval, interpolating crossings at 0/-6/-12/-18°.

    Fractional sample indices give shared boundaries without gaps or overlap.
    """
    thresholds = (0, -6, -12, -18)
    spans: list[tuple[float, float, int]] = []
    for i, (left, right) in enumerate(zip(sun_altitudes_deg[:-1], sun_altitudes_deg[1:])):
        cuts = [0.0, 1.0]
        if right != left:
            cuts += [(limit - left) / (right - left) for limit in thresholds
                     if min(left, right) < limit < max(left, right)]
        cuts.sort()
        for a, b in zip(cuts[:-1], cuts[1:]):
            middle = left + (right - left) * (a + b) / 2
            band = sum(middle <= limit for limit in thresholds)
            start, stop = i + a, i + b
            if spans and spans[-1][2] == band:
                spans[-1] = (spans[-1][0], stop, band)
            else:
                spans.append((start, stop, band))
    return spans


def build_altitude_chart(
    object_query: str, instant: Time, latitude_deg: float, longitude_deg: float,
    height_m: float, output_png: Path, language: str = "EN", time_mode: str = "UTC",
    moon_output_png: Path | None = None,
    min_altitude_deg: float = 0.0, sun_limit_deg: float = -12.0,
    return_details: bool = False,
) -> Path | AltitudeChartResult:
    """Render the selected night at five-minute steps with shared observing criteria.

    The envelope is local solar noon to noon; ticks use the selected civil
    timezone or UTC. Longitude is normalized to [-180, 180). The marked maximum
    satisfies observing constraints; it is sampled, not an exact meridian transit.
    """
    if not np.isfinite([latitude_deg, longitude_deg, height_m]).all() or not -90 <= latitude_deg <= 90:
        raise ValueError("Invalid reference coordinates")
    longitude_deg = (longitude_deg + 180) % 360 - 180
    start, stop, _ = observing_night_window_utc(instant, longitude_deg)
    start, stop = start - 6 * u.hour, stop + 6 * u.hour
    ephemerides = query_horizons_range(object_query, start, stop, step="5m")
    rows = []
    for eph in ephemerides:
        t = _time_from_ephemeris(eph)
        altitude, azimuth, sun_altitude = altitude_at_reference_site(
            eph, t, latitude_deg, longitude_deg, height_m,
        )
        if not np.isfinite([altitude, sun_altitude]).all():
            raise ValueError("Invalid altitude sample")
        rows.append((t, altitude, sun_altitude, azimuth))
    rows.sort(key=lambda row: float(row[0].utc.jd))
    if len(rows) < 2:
        raise ValueError("Insufficient ephemerides for altitude chart")
    tr = Translator(language).tr
    tz_name, tz = timezone_from_reference(latitude_deg, longitude_deg) if time_mode.upper() == "LOCAL" else ("UTC", timezone.utc)
    dates = [row[0].to_datetime(timezone=timezone.utc) for row in rows]
    altitude = np.array([row[1] for row in rows])
    sun = np.array([row[2] for row in rows])
    observation = observing_window_from_samples(
        [(i, row[0], row[1], row[3], row[2]) for i, row in enumerate(rows)], min_altitude_deg, sun_limit_deg)
    fig = Figure(figsize=(12, 4), dpi=140, facecolor="#263238")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, facecolor="#151d22")
    try:
        bands = [("#34444b", "Day"), ("#71808c", "Civil twilight"),
                 ("#505f6b", "Nautical twilight"), ("#35434f", "Astronomical twilight"),
                 ("#151d22", "Night")]
        def sample_date(index: float):
            i = min(int(index), len(dates) - 2)
            return dates[i] + (dates[i + 1] - dates[i]) * (index - i)
        for left, right, band in twilight_spans(sun):
            ax.axvspan(sample_date(left), sample_date(right), facecolor=bands[band][0],
                       edgecolor="none", linewidth=0, antialiased=False)
        legend_handles = [Patch(facecolor=color, label=tr(label)) for color, label in bands[:4]]
        ax.plot(dates, altitude, color="#69c7df", linewidth=1.8)
        optimum = observation["best"]
        best = optimum.ephemeris_index
        if best is not None:
            legend_handles.append(Patch(facecolor="#76cf9b", alpha=.25, label=tr("Observing window")))
            ax.axvspan(observation["window_start"].to_datetime(timezone=timezone.utc),
                       observation["window_stop"].to_datetime(timezone=timezone.utc), color="#76cf9b", alpha=.1)
            ax.scatter([dates[best]], [altitude[best]], color="#d8e4ec", zorder=4)
            ax.annotate(f"{format_number(altitude[best], 1, language, False)}° · {dates[best].astimezone(tz):%H:%M}\n{tr('Best time')}",
                        (dates[best], altitude[best]), xytext=(0, -30),
                        textcoords="offset points", ha="center", color="#d8e4ec", fontsize=9)
        else:
            ax.text(.5, .5, tr("No eligible observing window"),
                    transform=ax.transAxes, ha="center", color="#d8e4ec")
        now = Time.now().to_datetime(timezone=timezone.utc)
        if dates[0] <= now <= dates[-1]:
            ax.axvline(now, color="#c6d3db", linestyle="--", linewidth=1)
            ax.text(now, 5, tr("Now"), rotation=90, va="bottom", color="#c6d3db")
        ax.set(xlim=(dates[0], dates[-1]), ylim=(0, 90), yticks=[0, 30, 60, 90],
               ylabel=tr("Altitude (°)"), xlabel=f"{dates[0].astimezone(tz):%Y-%m-%d} — {dates[-1].astimezone(tz):%Y-%m-%d} · {tz_name}")
        ax.xaxis.set_major_locator(HourLocator(byhour=range(0, 24, 3), tz=tz))
        ax.xaxis.set_major_formatter(DateFormatter("%H:%M", tz=tz))
        ax.grid(axis="y", color="#9cabb5", linestyle="--", alpha=.25)
        ax.tick_params(colors="#c6d3db")
        ax.xaxis.label.set_color("#c6d3db")
        ax.yaxis.label.set_color("#c6d3db")
        for spine in ax.spines.values():
            spine.set_color("#54616a")
        sources = ", ".join(sorted({eph.source for eph in ephemerides}))
        ax.set_title(f"{ephemerides[0].target_name} · {tr('Altitude chart')}\n{latitude_deg:.3f}°, {longitude_deg:.3f}° · {height_m:g} m · {sources}", color="#e9f0f7", fontsize=11, pad=14)
        ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(.5, -.24), ncol=len(legend_handles),
                  facecolor="#263238", labelcolor="#c6d3db", frameon=False, fontsize=8)
        fig.subplots_adjust(left=.07, right=.98, top=.78, bottom=.3)
        output_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_png, facecolor=fig.get_facecolor())
        if moon_output_png is not None:
            times = Time([float(row[0].utc.jd) for row in rows], format="jd", scale="utc")
            lunar_altitude = moon_altitudes_deg(times, latitude_deg, longitude_deg, height_m)
            moon_line, = ax.plot(dates, lunar_altitude, color="white", alpha=.4,
                                 linewidth=1.6, label=tr("Moon"))
            ax.legend(handles=[*legend_handles, moon_line], loc="upper center",
                      bbox_to_anchor=(.5, -.24), ncol=len(legend_handles)+1, facecolor="#263238",
                      labelcolor="#c6d3db", frameon=False, fontsize=8)
            fig.savefig(moon_output_png, facecolor=fig.get_facecolor())
        return AltitudeChartResult(output_png, observation) if return_details else output_png
    finally:
        fig.clear()
