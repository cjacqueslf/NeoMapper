from dataclasses import dataclass

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord, EarthLocation, GCRS, AltAz, get_sun, get_body
from astropy.time import Time

AU_KM = 149_597_870.700


def moon_altitudes_deg(times: Time, latitude_deg: float, longitude_deg: float,
                       height_m: float = 0.0) -> np.ndarray:
    """Airless topocentric lunar altitudes using Astropy's builtin ephemeris.

    Longitude is normalized to [-180, 180); the observer height is in metres.
    """
    location = EarthLocation(lat=latitude_deg * u.deg,
                             lon=((longitude_deg + 180) % 360 - 180) * u.deg,
                             height=height_m * u.m)
    moon = get_body("moon", times, location=location, ephemeris="builtin")
    frame = AltAz(obstime=times, location=location, pressure=0 * u.hPa)
    return np.asarray(moon.transform_to(frame).alt.to_value(u.deg))

@dataclass(frozen=True)
class BestAltitudeResult:
    altitude_deg: float | None
    time: Time | None
    az_deg: float | None = None
    sun_alt_deg: float | None = None
    ephemeris_index: int | None = None
    reason: str = "ok"

    @property
    def observable(self) -> bool:
        return self.altitude_deg is not None and self.altitude_deg > 0

def make_grid(step_deg: float):
    lons = np.arange(-180.0, 180.0 + step_deg, step_deg)
    lats = np.arange(-89.5, 89.5 + step_deg, step_deg)
    return np.meshgrid(lons, lats)

def target_vector_gcrs(h, t):
    coord = SkyCoord(
        ra=h.ra_deg * u.deg,
        dec=h.dec_deg * u.deg,
        distance=(h.delta_au * u.au).to(u.km),
        frame=GCRS(obstime=t),
    )
    c = coord.cartesian
    return np.array([c.x.to_value(u.km), c.y.to_value(u.km), c.z.to_value(u.km)], dtype=float)

def observer_vectors_gcrs(t, lon2d, lat2d):
    loc = EarthLocation(
        lon=lon2d.ravel() * u.deg,
        lat=lat2d.ravel() * u.deg,
        height=np.zeros(lon2d.size) * u.m,
    )
    pos, _ = loc.get_gcrs_posvel(t)
    return np.vstack([pos.x.to_value(u.km), pos.y.to_value(u.km), pos.z.to_value(u.km)]).T

def altitude_topocentric_grid(h, t, lon2d, lat2d):
    target = target_vector_gcrs(h, t)
    obs = observer_vectors_gcrs(t, lon2d, lat2d)
    topo = target.reshape(1, 3) - obs
    topo_norm = np.linalg.norm(topo, axis=1)
    los = topo / topo_norm[:, None]
    up = obs / np.linalg.norm(obs, axis=1)[:, None]
    sin_alt = np.sum(los * up, axis=1)
    alt = np.degrees(np.arcsin(np.clip(sin_alt, -1.0, 1.0)))
    return alt.reshape(lon2d.shape), topo_norm.reshape(lon2d.shape)

def sun_altitude_grid(t, lon2d, lat2d):
    sun = get_sun(t)
    loc = EarthLocation(
        lon=lon2d.ravel() * u.deg,
        lat=lat2d.ravel() * u.deg,
        height=np.zeros(lon2d.size) * u.m,
    )
    return sun.transform_to(AltAz(obstime=t, location=loc)).alt.deg.reshape(lon2d.shape)

def max_altitude_point(alt, lon2d, lat2d):
    idx = np.unravel_index(np.nanargmax(alt), alt.shape)
    return float(lat2d[idx]), float(lon2d[idx]), float(alt[idx])

def _time_from_ephemeris(eph):
    jd = getattr(eph, "jd", None)
    if jd is not None:
        return Time(float(jd), format="jd", scale="utc")
    utc_iso = getattr(eph, "utc_iso", None)
    if utc_iso:
        return Time(str(utc_iso), scale="utc")
    raise ValueError("Ephemeris item has no usable time")

def altitude_at_reference_site(eph, t: Time, ref_lat: float, ref_lon: float, ref_height_m: float = 0.0):
    """Return (object altitude, object azimuth, Sun altitude) for one ephemeris at the reference site."""
    loc = EarthLocation(lon=float(ref_lon) * u.deg, lat=float(ref_lat) * u.deg, height=float(ref_height_m) * u.m)
    target = SkyCoord(
        ra=float(eph.ra_deg) * u.deg,
        dec=float(eph.dec_deg) * u.deg,
        distance=(float(eph.delta_au) * u.au).to(u.km),
        frame=GCRS(obstime=t),
    )
    altaz_frame = AltAz(obstime=t, location=loc)
    target_altaz = target.transform_to(altaz_frame)
    sun_altaz = get_sun(t).transform_to(altaz_frame)
    return float(target_altaz.alt.deg), float(target_altaz.az.deg), float(sun_altaz.alt.deg)


def observing_night_window_utc(t: Time, ref_lon: float):
    """
    Return a stable UTC search window for the observational night that contains t.

    The selected map time only chooses the observational night. The best-time
    search window remains the same for any instant inside that night. A simple
    local-solar conversion by longitude is used here to avoid requiring OS time
    zone data and to keep the result stable worldwide.

    Window definition: local solar 18:00 to next local solar 06:00. The Sun
    altitude filter is applied later to all sampled points, so this broad range
    is only the search envelope.
    """
    from datetime import datetime, timedelta, time as dtime

    offset_hours = float(ref_lon) / 15.0
    dt_utc = t.utc.datetime.replace(tzinfo=None)
    dt_local = dt_utc + timedelta(hours=offset_hours)

    # Before local noon, the instant belongs to the previous evening's night.
    night_date = dt_local.date() if dt_local.hour >= 12 else (dt_local.date() - timedelta(days=1))
    local_start = datetime.combine(night_date, dtime(18, 0, 0))
    local_stop = local_start + timedelta(hours=12)

    utc_start = local_start - timedelta(hours=offset_hours)
    utc_stop = local_stop - timedelta(hours=offset_hours)
    return Time(utc_start, scale="utc"), Time(utc_stop, scale="utc"), night_date

def best_altitude_during_night(ephemerides, ref_lat: float, ref_lon: float, sun_limit_deg: float = -12.0):
    """
    Find the best object altitude at the reference site during the whole period
    where the Sun altitude is lower than sun_limit_deg.

    This is a window filter, not a calculation at the exact -12 degree crossing.
    Every sampled ephemeris with Sun altitude < -12 deg is eligible.
    """
    best = None
    found_night = False

    for i, eph in enumerate(ephemerides or []):
        try:
            t = _time_from_ephemeris(eph)
            obj_alt, obj_az, sun_alt = altitude_at_reference_site(eph, t, ref_lat, ref_lon)
        except Exception:
            continue

        if sun_alt < float(sun_limit_deg):
            found_night = True
            if best is None or obj_alt > best.altitude_deg:
                best = BestAltitudeResult(
                    altitude_deg=obj_alt,
                    time=t,
                    az_deg=obj_az,
                    sun_alt_deg=sun_alt,
                    ephemeris_index=i,
                    reason="ok" if obj_alt > 0 else "below_horizon",
                )

    if best is None:
        return BestAltitudeResult(None, None, reason="no_sun_below_limit" if not found_night else "no_valid_ephemeris")
    if best.altitude_deg <= 0:
        return BestAltitudeResult(best.altitude_deg, best.time, best.az_deg, best.sun_alt_deg, best.ephemeris_index, "below_horizon")
    return best


def observational_window_and_best(ephemerides, ref_lat: float, ref_lon: float, min_altitude_deg: float = 0.0, sun_limit_deg: float = -18.0, height_m: float = 0.0):
    """
    Observational window = astronomical darkness intersected with object altitude >= min_altitude_deg.
    Returns dict with sampled start/stop and best altitude inside that interval.
    """
    observations = []
    for i, eph in enumerate(ephemerides or []):
        try:
            t = _time_from_ephemeris(eph)
            obj_alt, obj_az, sun_alt = altitude_at_reference_site(eph, t, ref_lat, ref_lon, height_m)
        except Exception:
            continue
        observations.append((i, t, obj_alt, obj_az, sun_alt))

    return observing_window_from_samples(observations, min_altitude_deg, sun_limit_deg)


def observing_window_from_samples(observations: list[tuple[int, Time, float, float, float]],
                                  min_altitude_deg: float = 0.0, sun_limit_deg: float = -18.0) -> dict:
    """Select a continuous observing window from shared altitude/azimuth/Sun samples."""
    # Provider responses are expected in chronological order, but sorting here
    # keeps the scientific result deterministic if that contract is violated.
    observations.sort(key=lambda row: float(row[1].utc.jd))
    all_dark = [row for row in observations if row[4] <= float(sun_limit_deg)]

    # An observing window must be continuous. Split eligible samples whenever
    # an intervening sample is not dark or is below the requested altitude.
    segments = []
    current = []
    for row in observations:
        eligible = row[4] <= float(sun_limit_deg) and row[2] >= float(min_altitude_deg)
        if eligible:
            current.append(row)
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)

    result = {
        "dark_start": all_dark[0][1] if all_dark else None,
        "dark_stop": all_dark[-1][1] if all_dark else None,
        "window_start": None,
        "window_stop": None,
        "min_altitude_deg": float(min_altitude_deg),
        "sun_limit_deg": float(sun_limit_deg),
        "best": BestAltitudeResult(None, None, reason="no_astronomical_darkness" if not all_dark else "not_above_min_altitude"),
    }
    if not segments:
        return result

    # The current UI presents one window, so report the continuous segment
    # containing the best observable sample of the night.
    selected = max(segments, key=lambda segment: max(row[2] for row in segment))
    result["window_start"] = selected[0][1]
    result["window_stop"] = selected[-1][1]
    best_i, best_t, best_alt, best_az, best_sun_alt = max(selected, key=lambda row: row[2])
    result["best"] = BestAltitudeResult(best_alt, best_t, best_az, best_sun_alt, best_i, "ok")
    return result
