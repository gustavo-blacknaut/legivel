import re
from dataclasses import dataclass
from datetime import date

from app.ocr.base import TextBox

MRZ_LINE = re.compile(r"^[A-Z0-9<]{25,44}$")
WEIGHTS = (7, 3, 1)


@dataclass(frozen=True)
class MrzData:
    raw: str
    document_number: str
    birth_date: date | None
    expiry_date: date | None
    surname: str
    given_names: str
    checks_valid: bool


def char_value(char: str) -> int:
    if char.isdigit():
        return int(char)
    if char == "<":
        return 0
    return ord(char) - ord("A") + 10


def check_digit(data: str) -> str:
    return str(sum(char_value(char) * WEIGHTS[index % 3] for index, char in enumerate(data)) % 10)


def parse_mrz_date(value: str, future: bool) -> date | None:
    if not value.isdigit():
        return None
    year, month, day = int(value[:2]), int(value[2:4]), int(value[4:6])
    current = date.today().year % 100
    century = 2000 if (year <= current + (20 if future else 0)) else 1900
    try:
        return date(century + year, month, day)
    except ValueError:
        return None


def clean_mrz_line(text: str) -> str:
    return re.sub(r"\s", "", text.upper()).replace("«", "<").replace("K<", "<<") if "<" in text else ""


def find_mrz_lines(boxes: list[TextBox]) -> list[str]:
    candidates = [(box.y0, clean_mrz_line(box.text)) for box in boxes]
    lines = [line for _, line in sorted(candidates) if MRZ_LINE.match(line) and line.count("<") >= 2]
    return lines[-3:]


def parse_td1(lines: list[str]) -> MrzData | None:
    if len(lines) != 3:
        return None
    first, second, third = (line.ljust(30, "<")[:30] for line in lines)
    document_number = first[5:14]
    birth, expiry = second[0:6], second[8:14]
    checks_valid = (
        check_digit(document_number) == first[14]
        and check_digit(birth) == second[6]
        and check_digit(expiry) == second[14]
    )
    surname, _, given = third.partition("<<")
    return MrzData(
        raw="\n".join(lines),
        document_number=document_number.replace("<", ""),
        birth_date=parse_mrz_date(birth, future=False),
        expiry_date=parse_mrz_date(expiry, future=True),
        surname=surname.replace("<", " ").strip(),
        given_names=given.replace("<", " ").strip(),
        checks_valid=checks_valid,
    )


@dataclass(frozen=True)
class PassportMrz:
    raw: str
    document_type: str
    issuing_country: str
    surname: str
    given_names: str
    passport_number: str
    nationality: str
    birth_date: date | None
    sex: str
    expiry_date: date | None
    personal_number: str
    checks_valid: bool


def parse_td3(lines: list[str]) -> PassportMrz | None:
    if len(lines) != 2:
        return None
    first, second = (line.ljust(44, "<")[:44] for line in lines)
    if not first.startswith("P"):
        return None
    names = first[5:]
    surname, _, given = names.partition("<<")
    passport_number, birth, expiry, personal = second[0:9], second[13:19], second[21:27], second[28:42]
    composite = second[0:10] + second[13:20] + second[21:43]
    checks_valid = (
        check_digit(passport_number) == second[9]
        and check_digit(birth) == second[19]
        and check_digit(expiry) == second[27]
        and check_digit(personal) == (second[42] if second[42] != "<" else "0")
        and check_digit(composite) == second[43]
    )
    return PassportMrz(
        raw="\n".join(lines),
        document_type=first[0:2].replace("<", ""),
        issuing_country=first[2:5].replace("<", ""),
        surname=surname.replace("<", " ").strip(),
        given_names=given.replace("<", " ").strip(),
        passport_number=passport_number.replace("<", ""),
        nationality=second[10:13].replace("<", ""),
        birth_date=parse_mrz_date(birth, future=False),
        sex={"M": "Masculino", "F": "Feminino"}.get(second[20], "Não informado"),
        expiry_date=parse_mrz_date(expiry, future=True),
        personal_number=personal.replace("<", ""),
        checks_valid=checks_valid,
    )


def find_td3_lines(boxes: list[TextBox]) -> list[str]:
    candidates = [(box.y0, clean_mrz_line(box.text)) for box in boxes]
    lines = [line for _, line in sorted(candidates) if len(line) >= 40 and line.count("<") >= 3]
    return lines[-2:]
