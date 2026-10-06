import re
from collections.abc import Callable
from itertools import product

from legivel.ocr.base import TextBox
from legivel.parsers.base import ExtractedField
from legivel.parsers.layout import find_value, normalize
from legivel.validators.cpf import format_cpf, is_valid_cpf, only_digits
from legivel.validators.dates import format_brazilian_date, parse_brazilian_date

CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\s?[.,]?\s?\d{3}\s?[.,]?\s?\d{3}\s?[-.]?\s?\d{2}(?!\d)")
CPF_LIKE_PATTERN = re.compile(r"[\dOoIlSBZ]{3}\s?[.,]?\s?[\dOoIlSBZ]{3}\s?[.,]?\s?[\dOoIlSBZ]{3}\s?[-.]?\s?[\dOoIlSBZ]{2}")
DATE_PATTERN = re.compile(r"\d{1,2}\s?[/.\-]\s?\d{1,2}\s?[/.\-]\s?\d{2,4}")
STATES = "AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO"
AUTHORITIES = "SSP|SESP|SSPDS|SDS|SEJUSP|SESDEC|SSPCE|SJS|PCII|PC|IIRGD|IGP|IFP|DETRAN|DGPC|ITEP|IIPM|DIC|SEDS|POLITEC|SPTC|SJTC"
ISSUING_AUTHORITY_PATTERN = re.compile(rf"\b({AUTHORITIES})\s*[-/ ]?\s*({STATES})\b")
NAME_NOISE = re.compile(r"[^A-ZÀ-Ü' ]")
OCR_DIGIT_CONFUSIONS = {
    "O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1", "|": "1", "S": "5", "B": "8", "Z": "2", "G": "6",
}
AMBIGUOUS_DIGITS = {"1": "7", "7": "1", "5": "6", "6": "5", "8": "3", "3": "8", "0": "8"}
MAX_AMBIGUOUS_POSITIONS = 3


def looks_like_name(text: str) -> bool:
    cleaned = clean_name(text)
    return len(cleaned) >= 5 and " " in cleaned and not any(char.isdigit() for char in text)


def clean_name(text: str) -> str:
    return re.sub(r"\s+", " ", NAME_NOISE.sub(" ", text.upper())).strip()


def has_date(text: str) -> bool:
    return parse_brazilian_date(text) is not None


def has_cpf(text: str) -> bool:
    return CPF_PATTERN.search(normalize(text)) is not None


def with_value(field: ExtractedField, value: str) -> ExtractedField:
    return ExtractedField(value, field.confidence, field.box)


def as_name(field: ExtractedField | None) -> ExtractedField | None:
    return with_value(field, clean_name(field.value)) if field else None


def as_date(field: ExtractedField | None) -> ExtractedField | None:
    if field is None:
        return None
    parsed = parse_brazilian_date(field.value)
    return with_value(field, format_brazilian_date(parsed) if parsed else field.value)


def as_cpf(field: ExtractedField | None) -> ExtractedField | None:
    if field is None:
        return None
    match = CPF_PATTERN.search(normalize(field.value))
    digits = only_digits(match.group(0) if match else field.value)
    return with_value(field, format_cpf(digits))


def repair_cpf_candidates(text: str) -> list[str]:
    match = CPF_LIKE_PATTERN.search(text)
    if not match:
        return []
    translated = "".join(OCR_DIGIT_CONFUSIONS.get(char, char) for char in match.group(0))
    digits = only_digits(translated)
    if len(digits) != 11:
        return []
    if is_valid_cpf(digits):
        return [digits]
    ambiguous = [index for index, digit in enumerate(digits) if digit in AMBIGUOUS_DIGITS]
    if len(ambiguous) > MAX_AMBIGUOUS_POSITIONS * 3:
        return []
    valid = set()
    for count in range(1, MAX_AMBIGUOUS_POSITIONS + 1):
        for positions in product(ambiguous, repeat=count):
            if len(set(positions)) != count:
                continue
            candidate = list(digits)
            for position in positions:
                candidate[position] = AMBIGUOUS_DIGITS[candidate[position]]
            joined = "".join(candidate)
            if is_valid_cpf(joined):
                valid.add(joined)
        if valid:
            break
    return sorted(valid)


def find_issuing_authority(text: str) -> str | None:
    match = ISSUING_AUTHORITY_PATTERN.search(normalize(text))
    return f"{match.group(1)}/{match.group(2)}" if match else None


def first_present(*candidates: ExtractedField | None) -> ExtractedField | None:
    return next((candidate for candidate in candidates if candidate and candidate.value), None)


def extract_optional_fields(
    boxes: list[TextBox],
    labels: dict[str, tuple[str, ...]],
    all_labels: tuple[str, ...],
    accepts: Callable[[str], bool] = lambda text: len(text.strip()) >= 2,
) -> dict[str, ExtractedField | None]:
    return {name: find_value(boxes, variants, all_labels, accepts) for name, variants in labels.items()}
