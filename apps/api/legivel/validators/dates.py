import re
from datetime import date

DATE_PATTERN = re.compile(r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})")
MONTH_NAMES = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}
TEXTUAL_DATE_PATTERN = re.compile(r"(\d{1,2})\s*/?\s*(" + "|".join(MONTH_NAMES) + r")\w*\s*/?\s*(\d{4})")
TWO_DIGIT_YEAR_PIVOT = 30


def expand_year(year: int, reference_year: int) -> int:
    if year >= 100:
        return year
    century = (reference_year // 100) * 100
    candidate = century + year
    return candidate - 100 if candidate > reference_year + TWO_DIGIT_YEAR_PIVOT else candidate


def parse_brazilian_date(value: str, today: date | None = None) -> date | None:
    if not value:
        return None
    reference = today or date.today()
    text = value.upper()
    match = DATE_PATTERN.search(text)
    if match:
        day, month, year = (int(group) for group in match.groups())
    else:
        textual = TEXTUAL_DATE_PATTERN.search(text)
        if not textual:
            return None
        day, month, year = int(textual.group(1)), MONTH_NAMES[textual.group(2)], int(textual.group(3))
    try:
        return date(expand_year(year, reference.year), month, day)
    except ValueError:
        return None


def format_brazilian_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")
