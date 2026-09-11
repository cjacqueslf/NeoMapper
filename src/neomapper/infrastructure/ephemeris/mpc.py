from __future__ import annotations

from html.parser import HTMLParser
import math
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from astropy.time import Time
from neomapper.shared.version import APP_VERSION

MPC_EPHEMERIS_URL = "https://cgi.minorplanetcenter.net/cgi-bin/mpeph2.cgi"
AU_KM = 149_597_870.700


class MPCError(RuntimeError):
    """The MPC fallback did not return a usable ephemeris."""


class MPCNoEphemerisError(MPCError):
    """MPC responded but returned no ephemeris rows."""


class _ResponseParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_pre = False
        self.in_bold = False
        self.pre_blocks = []
        self.bold_blocks = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "pre":
            self.in_pre, self.parts = True, []
        elif tag.lower() == "b":
            self.in_bold, self.parts = True, []

    def handle_endtag(self, tag):
        if tag.lower() == "pre" and self.in_pre:
            self.pre_blocks.append("".join(self.parts))
            self.in_pre = False
        elif tag.lower() == "b" and self.in_bold:
            self.bold_blocks.append("".join(self.parts).strip())
            self.in_bold = False

    def handle_data(self, data):
        if self.in_pre or self.in_bold:
            self.parts.append(data)


_ROW_RE = re.compile(
    r"^\s*(?P<y>\d{4})\s+(?P<mo>\d{2})\s+(?P<d>\d{2})\s+(?P<hms>\d{6})\s+"
    r"(?P<rah>\d{1,2})\s+(?P<ram>\d{2})\s+(?P<ras>[\d.]+)\s+"
    r"(?P<sgn>[+-])(?P<dd>\d{1,2})\s+(?P<dm>\d{2})\s+(?P<ds>[\d.]+)\s+"
    r"(?P<delta>[\d.]+)\s+\S+\s+\S+\s+\S+\s+(?P<v>\S+)"
)


def _optional_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def parse_mpc_response(html: str, original_query: str) -> list[dict]:
    """Parse full-sexagesimal output from MPC's public MPES service."""
    parser = _ResponseParser()
    parser.feed(html)
    target = str(original_query).strip()
    if parser.bold_blocks:
        target = " ".join(parser.bold_blocks[0].split())

    rows = []
    for block in parser.pre_blocks:
        for line in block.splitlines():
            match = _ROW_RE.match(line)
            if not match:
                continue
            p = match.groupdict()
            hms = p["hms"]
            utc = f'{p["y"]}-{p["mo"]}-{p["d"]} {hms[:2]}:{hms[2:4]}:{hms[4:]}'
            ra = 15 * (int(p["rah"]) + int(p["ram"]) / 60 + float(p["ras"]) / 3600)
            dec = int(p["dd"]) + int(p["dm"]) / 60 + float(p["ds"]) / 3600
            if p["sgn"] == "-":
                dec = -dec
            delta = float(p["delta"])
            rows.append({
                "target_name": target,
                "utc_iso": utc,
                "ra_deg": ra,
                "dec_deg": dec,
                "distance_au": delta,
                "distance_km": delta * AU_KM,
                "vmag": _optional_float(p["v"]),
                "jd": float(Time(utc, scale="utc").jd),
            })
    if not rows:
        detail = " ".join(" ".join(x.split()) for x in parser.pre_blocks)[:240] or "no ephemeris rows"
        raise MPCNoEphemerisError(f"MPC did not return an ephemeris for {original_query!r}: {detail}")
    return rows


def _step_parts(step):
    match = re.fullmatch(r"\s*(\d+)\s*([mhd])\s*", str(step), re.I)
    if not match:
        raise ValueError(f"Unsupported ephemeris step {step!r}")
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if not 1 <= amount <= 999:
        raise ValueError("MPC interval must be between 1 and 999")
    days = amount / 1440 if unit == "m" else amount / 24 if unit == "h" else float(amount)
    return amount, unit, days


def _request_mpc(object_query, start, count, step, timeout=25.0):
    amount, unit, _ = _step_parts(step)
    if not 1 <= count <= 9999:
        raise ValueError("MPC request must contain 1 to 9999 dates")
    fields = [
        ("ty", "e"), ("TextArea", str(object_query).strip()),
        ("d", start.utc.strftime("%Y-%m-%d %H:%M:%S")), ("l", str(count)),
        ("i", str(amount)), ("u", unit), ("uto", "0"), ("c", ""),
        ("long", ""), ("lat", ""), ("alt", ""), ("raty", "a"),
        ("s", "t"), ("m", "m"), ("adir", "N"), ("oed", ""),
        ("e", "-2"), ("resoc", ""), ("tit", ""), ("bu", ""),
        ("ch", "c"), ("ce", "f"), ("js", "f"),
    ]
    request = Request(
        MPC_EPHEMERIS_URL,
        data=urlencode(fields).encode("ascii"),
        method="POST",
        headers={"User-Agent": f"NEOMapper/{APP_VERSION}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("latin-1", errors="replace")
    except Exception as exc:
        raise MPCError(f"MPC ephemeris request failed: {exc}") from exc
    return parse_mpc_response(html, object_query)


def query_mpc(object_query, t):
    return _request_mpc(object_query, t, 1, "1h")[0]


def query_mpc_range(object_query, start, stop, step="10m"):
    _, _, step_days = _step_parts(step)
    span = max(0.0, float(stop.utc.jd - start.utc.jd))
    count = int(math.floor(span / step_days + 1e-9)) + 1
    return _request_mpc(object_query, start, count, step)
