import unittest
from unittest.mock import patch

from astropy.time import Time

from neomapper.application import ephemerides
from neomapper.infrastructure.ephemeris.mpc import MPCError, MPCNoEphemerisError, parse_mpc_response

SAMPLE = """<html><body><b> (99942) Apophis</b><pre>
99942 [H=19.00]
Date UT R.A. (J2000) Decl.
2029 04 13 220000 07 33 46.3 +33 35 46   0.00026 1.003 86.0 94.0 4.4 2363.43 291.9 N/A N/A /
2029 04 13 230000 04 53 20.2 -09 30 00   0.00032 1.003 54.5 125.5 N/A 1476.69 267.4 N/A N/A /
</pre></body></html>"""

MPC_ROW = {
    "target_name": "(99942) Apophis", "utc_iso": "2029-04-13 22:00:00",
    "ra_deg": 113.4429167, "dec_deg": 33.5961111,
    "distance_au": 0.00026, "distance_km": 38895.446382,
    "vmag": 4.4, "jd": 2462240.4166667,
}


class MPCParserTests(unittest.TestCase):
    def test_parses_coordinates_distance_magnitude_and_missing_magnitude(self):
        rows = parse_mpc_response(SAMPLE, "99942")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["target_name"], "(99942) Apophis")
        self.assertAlmostEqual(rows[0]["ra_deg"], 113.4429167, places=5)
        self.assertAlmostEqual(rows[0]["dec_deg"], 33.5961111, places=5)
        self.assertEqual(rows[0]["vmag"], 4.4)
        self.assertAlmostEqual(rows[1]["dec_deg"], -9.5)
        self.assertIsNone(rows[1]["vmag"])

    def test_rejects_response_without_ephemeris(self):
        with self.assertRaises(MPCError):
            parse_mpc_response("<html><pre>object not found</pre></html>", "missing")


class ProviderFallbackTests(unittest.TestCase):
    def test_unknown_target_with_empty_mpc_response_is_not_found(self):
        with patch.object(ephemerides, "_query_ephemerides", side_effect=ValueError("Unknown target (2200P). Maybe try different id_type?")), patch.object(
            ephemerides, "query_mpc", side_effect=MPCNoEphemerisError("no ephemeris rows")
        ):
            with self.assertRaises(ephemerides.ObjectNotFoundError):
                ephemerides.query_horizons("2200P", Time("2026-09-08", scale="utc"))

    def test_connection_failures_are_not_reported_as_missing_objects(self):
        for jpl, mpc in [
            (ValueError("Unknown target"), MPCError("request failed: timeout")),
            (TimeoutError("timeout"), MPCNoEphemerisError("no ephemeris rows")),
            (ValueError("Ambiguous target name"), MPCNoEphemerisError("no ephemeris rows")),
        ]:
            self.assertNotIsInstance(ephemerides._fallback_error(jpl, mpc), ephemerides.ObjectNotFoundError)

    def test_single_query_falls_back_to_mpc(self):
        with patch.object(ephemerides, "_query_ephemerides", side_effect=OSError("JPL unavailable")), \
             patch.object(ephemerides, "query_mpc", return_value=MPC_ROW):
            result = ephemerides.query_horizons("99942", Time("2029-04-13 22:00:00", scale="utc"))
        self.assertEqual(result.source, "MPC fallback")
        self.assertEqual(result.target_name, "(99942) Apophis")
        self.assertAlmostEqual(result.distance_au, 0.00026)

    def test_range_query_falls_back_to_mpc(self):
        start = Time("2029-04-13 22:00:00", scale="utc")
        stop = Time("2029-04-13 23:00:00", scale="utc")
        with patch.object(ephemerides, "Horizons") as jpl, \
             patch.object(ephemerides, "query_mpc_range", return_value=[MPC_ROW, dict(MPC_ROW, utc_iso="2029-04-13 23:00:00")]):
            jpl.return_value.ephemerides.side_effect = TimeoutError("JPL timeout")
            results = ephemerides.query_horizons_range("99942", start, stop, "1h")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(item.source == "MPC fallback" for item in results))

    def test_reports_both_provider_errors(self):
        with patch.object(ephemerides, "_query_ephemerides", side_effect=OSError("JPL down")), \
             patch.object(ephemerides, "query_mpc", side_effect=MPCError("MPC down")):
            with self.assertRaisesRegex(RuntimeError, "Both ephemeris providers failed"):
                ephemerides.query_horizons("99942", Time("2029-04-13", scale="utc"))


if __name__ == "__main__":
    unittest.main()
