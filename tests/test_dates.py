from datetime import date

import pytest

from app.validators.dates import expand_year, format_brazilian_date, parse_brazilian_date

TODAY = date(2026, 10, 2)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("15/03/1990", date(1990, 3, 15)),
        ("15.03.1990", date(1990, 3, 15)),
        ("15-03-1990", date(1990, 3, 15)),
        ("5/3/1990", date(1990, 3, 5)),
        ("15 / 03 / 1990", date(1990, 3, 15)),
        ("DATA NASC. 01/01/2000 X", date(2000, 1, 1)),
        ("15/MAR/1990", date(1990, 3, 15)),
        ("15 MARÇO 1990", date(1990, 3, 15)),
        ("15/03/90", date(1990, 3, 15)),
        ("15/03/30", date(2030, 3, 15)),
    ],
)
def test_parses_brazilian_dates(text, expected):
    assert parse_brazilian_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["31/02/1990", "15/13/1990", "", "sem data", "00/00/0000"])
def test_rejects_invalid_dates(text):
    assert parse_brazilian_date(text, TODAY) is None


def test_expand_year_uses_pivot():
    assert expand_year(56, 2026) == 2056
    assert expand_year(57, 2026) == 1957
    assert expand_year(1985, 2026) == 1985


def test_format_brazilian_date():
    assert format_brazilian_date(date(1990, 3, 5)) == "05/03/1990"
