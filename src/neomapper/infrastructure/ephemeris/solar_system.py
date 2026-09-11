"""Load one geometric heliocentric state for the Solar System plot."""
import numpy as np
from astropy.time import Time
from astroquery.jplhorizons import Horizons

from neomapper.application.solar_system import ObjectOrbit, object_orbit
from neomapper.infrastructure.ephemeris.summary import HorizonsSummaryProvider


def load_object_orbit(query: str, instant: Time) -> ObjectOrbit:
    target = HorizonsSummaryProvider().resolve(query, instant)
    identifier = target.horizons_id or target.spk_id
    provider = Horizons(id=identifier, id_type=None if ";" in identifier else "designation",
                        location="500@10", epochs=float(instant.tdb.jd))
    provider.TIMEOUT = 20
    row = provider.vectors(refplane="ecliptic", aberrations="geometric")[0]
    position = np.array([float(row[key]) for key in ("x", "y", "z")])
    velocity = np.array([float(row[key]) for key in ("vx", "vy", "vz")])
    return object_orbit(target.name, position, velocity)
