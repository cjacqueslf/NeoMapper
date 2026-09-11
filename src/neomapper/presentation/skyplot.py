"""Pure helpers for rendering targets on altitude/azimuth sky plots."""

from __future__ import annotations

from collections.abc import Iterable

from astropy import units as u
from astropy.coordinates import AltAz, BaseCoordinateFrame, GCRS, SkyCoord
from astropy.time import Time


def visible_target_path(
    object_azimuth_deg: float,
    object_altitude_deg: float,
    trail_positions: Iterable[tuple[float, float] | tuple[float, float, str]] | None,
) -> list[tuple[float, float]]:
    """Return only target positions that belong above the geometric horizon."""
    visible = [
        (float(azimuth), float(altitude))
        for azimuth, altitude in (trail_positions or [])
        if altitude >= 0.0
    ]
    if object_altitude_deg >= 0.0:
        visible.append((float(object_azimuth_deg), float(object_altitude_deg)))
    return visible


def celestial_trail_to_horizontal(
    trail_positions: Iterable[tuple[float, float]] | None,
    horizontal_frame: BaseCoordinateFrame,
) -> list[tuple[float, float]]:
    """Project RA/Dec trail marks onto the current horizontal sky frame.

    Trail samples are stored on the celestial sphere instead of in the local
    AltAz frame. Reprojecting every sample for each animation instant makes
    existing marks rotate with the stellar background.
    """
    positions = list(trail_positions or [])
    if not positions:
        return []

    # Each sample retains its observation instant. This is important because
    # Horizons RA/Dec values are apparent GCRS coordinates at that instant;
    # treating all of them as coordinates of the current frame distorts the
    # historical path and produces a spurious final segment.
    horizontal_coords = []
    for sample in positions:
        if len(sample) >= 3:
            # Animation samples are the exact Alt/Az coordinates rendered in
            # the previous frame. Carry them through the celestial sphere to
            # the current frame, avoiding any mismatch with Horizons RA/Dec.
            azimuth, altitude, sample_time = sample[:3]
            coordinate = SkyCoord(
                az=float(azimuth) * u.deg,
                alt=float(altitude) * u.deg,
                frame=AltAz(
                    obstime=Time(sample_time, scale="utc"),
                    location=horizontal_frame.location,
                ),
            )
        else:
            ra, dec = sample[:2]
            coordinate = SkyCoord(ra=float(ra) * u.deg, dec=float(dec) * u.deg, frame="icrs")
        # Astropy cannot concatenate SkyCoord objects with different obstime
        # attributes; transform each historical sample independently.
        horizontal_coords.append(coordinate.transform_to(horizontal_frame))
    return [
        (float(horizontal.az.deg), float(horizontal.alt.deg))
        for horizontal in horizontal_coords
    ]
