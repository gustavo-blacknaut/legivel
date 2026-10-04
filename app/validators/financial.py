from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.validators.cpf import only_digits

BANK_SLIP_LENGTH = 47
COLLECTION_SLIP_LENGTH = 48
NFE_KEY_LENGTH = 44
CNPJ_LENGTH = 14
DUE_FACTOR_BASE = date(1997, 10, 7)
DUE_FACTOR_RESET = date(2025, 2, 22)
DUE_FACTOR_RESET_VALUE = 1000


def modulo10(digits: str) -> int:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char) * (2 if index % 2 == 0 else 1)
        total += value // 10 + value % 10
    return (10 - total % 10) % 10


def modulo11(digits: str, weights_up_to: int = 9) -> int:
    total = 0
    weight = 2
    for char in reversed(digits):
        total += int(char) * weight
        weight = 2 if weight == weights_up_to else weight + 1
    return total % 11


def bank_barcode_check_digit(barcode_without_dv: str) -> int:
    remainder = modulo11(barcode_without_dv)
    digit = 11 - remainder
    return 1 if digit in (0, 10, 11) else digit


def collection_check_digit(digits: str, value_indicator: str) -> int:
    if value_indicator in "67":
        return modulo10(digits)
    remainder = modulo11(digits)
    return 0 if remainder in (0, 1) else 11 - remainder


@dataclass(frozen=True)
class BankSlip:
    kind: str
    digitable_line: str
    barcode: str
    valid: bool
    amount: Decimal | None
    due_date: date | None
    bank_code: str | None


def due_date_from_factor(factor: int, today: date | None = None) -> date | None:
    if factor == 0:
        return None
    reference = today or date.today()
    original = DUE_FACTOR_BASE + timedelta(days=factor)
    reset = DUE_FACTOR_RESET + timedelta(days=factor - DUE_FACTOR_RESET_VALUE)
    return reset if abs((reset - reference).days) < abs((original - reference).days) else original


def parse_bank_slip(line: str, today: date | None = None) -> BankSlip | None:
    digits = only_digits(line)
    if len(digits) == BANK_SLIP_LENGTH:
        return parse_bank_line(digits, today)
    if len(digits) == COLLECTION_SLIP_LENGTH and digits[0] == "8":
        return parse_collection_line(digits)
    return None


def parse_bank_line(digits: str, today: date | None) -> BankSlip:
    fields = [(digits[0:9], digits[9]), (digits[10:20], digits[20]), (digits[21:31], digits[31])]
    fields_valid = all(modulo10(body) == int(dv) for body, dv in fields)
    barcode = digits[0:4] + digits[32] + digits[33:47] + digits[4:9] + digits[10:20] + digits[21:31]
    general_valid = bank_barcode_check_digit(barcode[:4] + barcode[5:]) == int(barcode[4])
    amount_cents = int(digits[37:47])
    return BankSlip(
        kind="bancario",
        digitable_line=digits,
        barcode=barcode,
        valid=fields_valid and general_valid,
        amount=Decimal(amount_cents) / 100 if amount_cents else None,
        due_date=due_date_from_factor(int(digits[33:37]), today),
        bank_code=digits[0:3],
    )


def parse_collection_line(digits: str) -> BankSlip:
    blocks = [digits[index : index + 12] for index in range(0, 48, 12)]
    value_indicator = digits[2]
    blocks_valid = all(collection_check_digit(block[:11], value_indicator) == int(block[11]) for block in blocks)
    barcode = "".join(block[:11] for block in blocks)
    general_valid = collection_check_digit(barcode[:3] + barcode[4:], value_indicator) == int(barcode[3])
    amount_cents = int(barcode[4:15]) if value_indicator in "68" else 0
    return BankSlip(
        kind="arrecadacao",
        digitable_line=digits,
        barcode=barcode,
        valid=blocks_valid and general_valid,
        amount=Decimal(amount_cents) / 100 if amount_cents else None,
        due_date=None,
        bank_code=None,
    )


def format_bank_line(digits: str) -> str:
    if len(digits) == BANK_SLIP_LENGTH:
        groups = (digits[0:5], digits[5:10], digits[10:15], digits[15:21], digits[21:26], digits[26:32])
        return f"{groups[0]}.{groups[1]} {groups[2]}.{groups[3]} {groups[4]}.{groups[5]} {digits[32]} {digits[33:47]}"
    if len(digits) == COLLECTION_SLIP_LENGTH:
        return " ".join(f"{digits[index : index + 11]}-{digits[index + 11]}" for index in range(0, 48, 12))
    return digits


def cnpj_check_digits(first_twelve: str) -> str:
    digits = [int(char) for char in first_twelve]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        total = sum(digit * weight for digit, weight in zip(digits, weights, strict=False))
        remainder = total % 11
        digits.append(0 if remainder < 2 else 11 - remainder)
    return f"{digits[-2]}{digits[-1]}"


def is_valid_cnpj(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != CNPJ_LENGTH or len(set(digits)) == 1:
        return False
    return cnpj_check_digits(digits[:12]) == digits[12:]


def format_cnpj(value: str) -> str:
    digits = only_digits(value)
    if len(digits) != CNPJ_LENGTH:
        return value
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def nfe_key_check_digit(first_43: str) -> int:
    remainder = modulo11(first_43)
    return 0 if remainder in (0, 1) else 11 - remainder


def is_valid_nfe_key(value: str) -> bool:
    digits = only_digits(value)
    return len(digits) == NFE_KEY_LENGTH and nfe_key_check_digit(digits[:43]) == int(digits[43])


def nfe_key_cnpj(value: str) -> str:
    return only_digits(value)[6:20]


def format_nfe_key(value: str) -> str:
    digits = only_digits(value)
    return " ".join(digits[index : index + 4] for index in range(0, len(digits), 4))


def parse_money(text: str) -> Decimal | None:
    cleaned = text.replace("R$", "").replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except ArithmeticError:
        return None
    except ValueError:
        return None


def format_money(amount: Decimal | None) -> str:
    if amount is None:
        return ""
    integer, cents = f"{amount:.2f}".split(".")
    groups = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    return f"R$ {'.'.join(groups)},{cents}"
