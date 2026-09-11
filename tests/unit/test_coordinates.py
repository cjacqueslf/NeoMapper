import pytest

from neomapper.presentation.coordinates import format_declination, format_right_ascension


@pytest.mark.parametrize("degrees, expected", [
    (0.0, "00h 00m 00.00s"),
    (51.0, "03h 24m 00.00s"),
    (188.73625, "12h 34m 56.70s"),
    (360.0, "00h 00m 00.00s"),
    (-15.0, "23h 00m 00.00s"),
    (359.999999, "00h 00m 00.00s"),
    (14.999999, "01h 00m 00.00s"),
    (None, "-"),
    (float("nan"), "-"),
])
def test_right_ascension(degrees: float | None, expected: str) -> None:
    assert format_right_ascension(degrees) == expected


@pytest.mark.parametrize("degrees, expected", [
    (-12.5824166667, '-12° 34\' 56.70"'),
    (-0.5, '-00° 30\' 00.00"'),
    (-0.0, '-00° 00\' 00.00"'),
    (12.9999999, '+13° 00\' 00.00"'),
    (-89.9999999, '-90° 00\' 00.00"'),
    (90.0, '+90° 00\' 00.00"'),
    (None, "-"),
    (float("inf"), "-"),
])
def test_declination(degrees: float | None, expected: str) -> None:
    assert format_declination(degrees) == expected


@pytest.mark.parametrize("language", ["PT", "pt-BR", "ES"])
def test_coordinate_decimal_separator(language: str) -> None:
    assert format_right_ascension(188.73625, language) == "12h 34m 56,70s"
    assert format_declination(-12.5824166667, language) == '-12° 34\' 56,70"'
