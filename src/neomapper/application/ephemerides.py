from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import re

from astropy.time import Time
from astroquery.jplhorizons import Horizons
from neomapper.infrastructure.ephemeris.mpc import MPCNoEphemerisError, query_mpc, query_mpc_range


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ephemeris:
    """
    Stable internal ephemeris contract for NEOMapper.

    All modules must use these canonical names:
    - target_name
    - utc_iso
    - ra_deg / dec_deg
    - az_deg / alt_deg
    - distance_au / distance_km
    - vmag
    """
    target_name: str
    utc_iso: str
    ra_deg: float
    dec_deg: float
    az_deg: float
    alt_deg: float
    distance_au: float
    distance_km: float
    delta_rate: float | None = None
    vmag: float | None = None
    sun_alt_deg: float | None = None
    moon_sep_deg: float | None = None
    horizons_record: str | None = None
    jd: float | None = None
    source: str = "JPL Horizons"

    # Backward-compatible aliases used by older core modules
    @property
    def targetname(self) -> str:
        return self.target_name

    @property
    def delta_au(self) -> float:
        return self.distance_au

    @property
    def ra(self) -> float:
        return self.ra_deg

    @property
    def dec(self) -> float:
        return self.dec_deg

    @property
    def az(self) -> float:
        return self.az_deg

    @property
    def el(self) -> float:
        return self.alt_deg


# Historical name kept for compatibility with older imports.
HorizonsResult = Ephemeris


def parse_utc(time_text: str) -> Time:
    """Parse UTC time text accepted by GUI/CLI."""
    value = (time_text or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return Time(datetime.strptime(value, fmt), scale="utc")
        except Exception:
            pass
    return Time(value, scale="utc")


def _extract_latest_record_id(error_text: str) -> str | None:
    """
    Extract the newest Horizons record from an ambiguous target list.

    Example row:
        90000395    2022    29P            29P             Schwassmann-Wachmann 1
    """
    candidates: list[tuple[int, str]] = []
    for line in error_text.splitlines():
        m = re.match(r"\s*(\d{6,})\s+(\d{4})\s+", line)
        if m:
            candidates.append((int(m.group(2)), m.group(1)))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def _query_ephemerides(object_query: str, t: Time):
    obj = Horizons(
        id=str(object_query).strip(),
        location="500@399",
        epochs=t.jd,
        id_type="designation" if "/" in str(object_query) else "smallbody",
    )
    return obj.ephemerides()


def _to_float_or_none(row, key: str):
    try:
        value = row[key]
        if value is None:
            return None
        text = str(value).strip()
        if not text or text in ("--", "n.a.", "None"):
            return None
        return float(value)
    except Exception:
        return None


def _row_to_ephemeris(row, original_query: str, resolved_record: str | None = None) -> Ephemeris:
    target_name = str(row["targetname"]) if "targetname" in row.colnames else str(original_query)

    distance_au = float(row["delta"])
    distance_km = distance_au * 149_597_870.700

    return Ephemeris(
        target_name=target_name,
        utc_iso=str(row["datetime_str"]) if "datetime_str" in row.colnames else "",
        ra_deg=float(row["RA"]),
        dec_deg=float(row["DEC"]),
        az_deg=float(row["AZ"]) if "AZ" in row.colnames else float("nan"),
        alt_deg=float(row["EL"]) if "EL" in row.colnames else float("nan"),
        distance_au=distance_au,
        distance_km=distance_km,
        delta_rate=_to_float_or_none(row, "delta_rate"),
        vmag=_to_float_or_none(row, "V"),
        sun_alt_deg=_to_float_or_none(row, "solar_presence"),
        moon_sep_deg=_to_float_or_none(row, "lunar_elong"),
        horizons_record=resolved_record,
        jd=_to_float_or_none(row, "datetime_jd"),
    )



def _mpc_row_to_ephemeris(row: dict) -> Ephemeris:
    return Ephemeris(
        target_name=row["target_name"], utc_iso=row["utc_iso"],
        ra_deg=float(row["ra_deg"]), dec_deg=float(row["dec_deg"]),
        az_deg=float("nan"), alt_deg=float("nan"),
        distance_au=float(row["distance_au"]), distance_km=float(row["distance_km"]),
        vmag=row.get("vmag"), jd=row.get("jd"), source="MPC fallback",
    )


class ObjectNotFoundError(RuntimeError):
    """The target was not resolved by JPL or the MPC fallback."""


def _fallback_error(jpl_error: Exception, mpc_error: Exception) -> RuntimeError:
    error_type = (
        ObjectNotFoundError
        if isinstance(jpl_error, ValueError)
        and "unknown target" in str(jpl_error).lower()
        and isinstance(mpc_error, MPCNoEphemerisError)
        else RuntimeError
    )
    return error_type(
        f"Both ephemeris providers failed. JPL Horizons: {jpl_error}; MPC: {mpc_error}"
    )


def query_report_ephemerides(object_query: str, start: Time, stop: Time, step: str,
                            latitude_deg: float, longitude_deg: float, max_rows: int = 500) -> list[dict]:
    """Observer report from Horizons native quantities, without rate approximations.

    UTC epochs; east-positive longitude normalized to [-180, 180), height 0 km.
    RA/DEC degrees, airless AZ/EL degrees, sky motion arcsec/minute,
    motion position angle degrees east of celestial north. No geocentric fallback.
    """
    if stop <= start:
        raise ValueError("End must be after start")
    from neomapper.application.generation_limits import enforce_limit, report_sample_count
    enforce_limit(report_sample_count(start, stop, step), max_rows)
    def query(target: str):
        return Horizons(id=target, id_type="smallbody", location={
            "lon": (longitude_deg + 180) % 360 - 180, "lat": latitude_deg, "elevation": 0.0,
        }, epochs={"start": start.utc.iso, "stop": stop.utc.iso, "step": step}).ephemerides(
            quantities="1,4,9,47", refraction=False)
    try:
        table = query(object_query)
    except ValueError as exc:
        record = _extract_latest_record_id(str(exc)) if "Ambiguous target name" in str(exc) else None
        if not record:
            raise
        table = query(record)
    enforce_limit(len(table), max_rows)
    return [{"target": str(row["targetname"]), "utc": Time(float(row["datetime_jd"]), format="jd", scale="utc").utc.isot,
             **{key: _to_float_or_none(row, key) for key in
                ("RA", "DEC", "AZ", "EL", "Sky_motion", "Sky_mot_PA", "V", "Tmag")}}
            for row in table]


def query_horizons_range(object_query: str, start: Time, stop: Time, step: str = "10m") -> list[Ephemeris]:
    """
    Query JPL Horizons geocentric ephemerides for a UTC time range.

    Used by the GUI panel to find the best altitude at the reference site
    during the whole nighttime window. The scientific map still uses the
    single instant selected by the user.
    """
    resolved_record = None
    epochs = {
        "start": start.utc.iso.replace(" ", "T"),
        "stop": stop.utc.iso.replace(" ", "T"),
        "step": step,
    }

    def _query_range(q):
        obj = Horizons(
            id=str(q).strip(),
            location="500@399",
            epochs=epochs,
            id_type="smallbody",
        )
        return obj.ephemerides()

    try:
        try:
            eph = _query_range(object_query)
        except ValueError as exc:
            msg = str(exc)
            if "Ambiguous target name" not in msg:
                raise
            resolved_record = _extract_latest_record_id(msg)
            if not resolved_record:
                raise
            eph = _query_range(resolved_record)
        return [_row_to_ephemeris(row, object_query, resolved_record) for row in eph]
    except Exception as jpl_error:
        logger.warning("JPL Horizons range query failed; trying MPC: %s", jpl_error)
        try:
            return [_mpc_row_to_ephemeris(row) for row in query_mpc_range(object_query, start, stop, step)]
        except Exception as mpc_error:
            raise _fallback_error(jpl_error, mpc_error) from mpc_error


def query_horizons(object_query: str, t: Time) -> Ephemeris:
    """
    Query JPL Horizons geocentric ephemeris and return a stable Ephemeris object.

    Handles ambiguous periodic comet names/designations such as 29P by selecting
    the record with the newest Epoch-yr from Horizons' ambiguity table.
    """
    try:
        resolved_record = None
        try:
            eph = _query_ephemerides(object_query, t)
        except ValueError as exc:
            msg = str(exc)
            if "Ambiguous target name" not in msg:
                raise
            resolved_record = _extract_latest_record_id(msg)
            if not resolved_record:
                raise
            eph = _query_ephemerides(resolved_record, t)
        return _row_to_ephemeris(eph[0], object_query, resolved_record)
    except Exception as jpl_error:
        logger.warning("JPL Horizons query failed; trying MPC: %s", jpl_error)
        try:
            return _mpc_row_to_ephemeris(query_mpc(object_query, t))
        except Exception as mpc_error:
            raise _fallback_error(jpl_error, mpc_error) from mpc_error
