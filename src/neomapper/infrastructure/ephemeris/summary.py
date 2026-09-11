"""JPL SBDB classification and Horizons values for the object summary."""
from __future__ import annotations

import math
import numpy as np
import requests
from astropy.time import Time
from astroquery.jplhorizons import Horizons
from neomapper.domain.object_summary import SummarySample, SummaryTarget


def optional_number(row: object, key: str) -> float | None:
    try:
        value = row[key]
        if np.ma.is_masked(value):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (KeyError, TypeError, ValueError):
        return None


class HorizonsSummaryProvider:
    def resolve(self, query: str, instant: Time) -> SummaryTarget:
        response = requests.get("https://ssd-api.jpl.nasa.gov/sbdb.api", params={"sstr": query}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if "object" not in payload:
            raise ValueError(f"SBDB: {payload.get('message', 'Object not uniquely identified')}")
        obj = payload["object"]
        if obj["kind"] not in ("cn", "cu", "an", "au"):
            raise ValueError("Unsupported SBDB object classification")
        is_comet = obj["kind"].startswith("c")
        # CAP fixes the apparition at the requested epoch, not at today's date.
        # Keep this same solution for every batch, including future event searches.
        designation = obj.get("des", obj["spkid"])
        identifier = f"DES={designation};CAP<{instant.tdb.jd:.8f};" if is_comet else obj["spkid"]
        provider = Horizons(id=identifier, id_type=None if is_comet else "designation", location="500@10", epochs=float(instant.tdb.jd))
        provider.TIMEOUT = 20
        elements = provider.elements(tp_type="absolute")
        tp = optional_number(elements[0], "Tp_jd")
        if tp is None:
            raise ValueError("Missing perihelion epoch")
        period = optional_number(elements[0], "P")
        eccentricity = optional_number(elements[0], "e")
        if period is not None and (period <= 0 or eccentricity is None or eccentricity >= 1):
            period = None
        return SummaryTarget(obj["fullname"], obj["spkid"], is_comet, Time(tp, format="jd", scale="tdb"), period, identifier)

    def samples(self, target: SummaryTarget, instants: Time) -> list[SummarySample]:
        result: list[SummarySample] = []
        epochs = np.atleast_1d(instants.utc.jd)
        for offset in range(0, len(epochs), 50):
            batch = epochs[offset:offset+50]
            order = np.argsort(batch)
            sorted_batch = batch[order]
            provider = Horizons(id=target.horizons_id or target.spk_id,
                                id_type=None if target.horizons_id and ";" in target.horizons_id else "designation",
                                location="500@399", epochs=sorted_batch.tolist())
            provider.TIMEOUT = 20
            table = provider.ephemerides(quantities="1,9,19,20,23,24,27", refraction=False, extra_precision=True)
            if len(table) != len(batch):
                raise ValueError("Incomplete summary ephemerides")
            batch_samples: list[SummarySample] = []
            for row, requested_jd in zip(table, sorted_batch):
                jd = optional_number(row, "datetime_jd")
                radius, delta = optional_number(row, "r"), optional_number(row, "delta")
                if jd is None or abs(jd-requested_jd) > 1e-7 or radius is None or delta is None or radius <= 0 or delta <= 0:
                    raise ValueError("Invalid summary epoch or distances")
                band = "T" if target.is_comet else "V"
                magnitude = optional_number(row, "Tmag" if target.is_comet else "V")
                if magnitude is None:
                    band = "V" if target.is_comet else "T"
                    magnitude = optional_number(row, "V" if target.is_comet else "Tmag")
                pa = optional_number(row, "sunTargetPA") if target.is_comet else None
                batch_samples.append(SummarySample(Time(jd, format="jd", scale="utc"), radius, delta,
                    optional_number(row, "RA"), optional_number(row, "DEC"), magnitude, band,
                    optional_number(row, "elong"), optional_number(row, "alpha"), None if pa is None else pa % 360))
            result.extend(batch_samples[i] for i in np.argsort(order))
        return result
