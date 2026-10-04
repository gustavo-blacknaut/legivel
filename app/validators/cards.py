import re
from dataclasses import dataclass
from datetime import date

from app.validators.cpf import only_digits

CARD_LENGTHS = range(12, 20)
BRAND_RULES: tuple[tuple[str, re.Pattern], ...] = (
    (
        "Elo",
        re.compile(
            r"^(401178|401179|431274|438935|451416|457393|457631|457632|504175|506699|5067\d\d|509\d{3}|627780|636297|636368|650\d{3}|651652|655000|655001)"
        ),
    ),
    ("Hipercard", re.compile(r"^(606282|3841)")),
    ("American Express", re.compile(r"^3[47]")),
    ("Diners Club", re.compile(r"^3(0[0-5]|[68])")),
    ("Discover", re.compile(r"^(6011|65|64[4-9])")),
    ("JCB", re.compile(r"^35(2[89]|[3-8])")),
    ("Mastercard", re.compile(r"^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d\d|27[01]\d|2720)")),
    ("Visa", re.compile(r"^4")),
)


def luhn_is_valid(number: str) -> bool:
    digits = only_digits(number)
    if len(digits) not in CARD_LENGTHS:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def card_brand(number: str) -> str | None:
    digits = only_digits(number)
    return next((brand for brand, pattern in BRAND_RULES if pattern.match(digits)), None)


def mask_card_number(number: str) -> str:
    digits = only_digits(number)
    return f"•••• •••• •••• {digits[-4:]}" if len(digits) >= 4 else "••••"


@dataclass(frozen=True)
class CardExpiry:
    month: int
    year: int

    @property
    def label(self) -> str:
        return f"{self.month:02d}/{self.year % 100:02d}"

    def is_expired(self, today: date | None = None) -> bool:
        reference = today or date.today()
        return (self.year, self.month) < (reference.year, reference.month)


EXPIRY_PATTERN = re.compile(r"(?<!\d)(0[1-9]|1[0-2])\s?/\s?(\d{2}|\d{4})(?!\d)")


def parse_expiry(text: str) -> CardExpiry | None:
    match = EXPIRY_PATTERN.search(text)
    if not match:
        return None
    year = int(match.group(2))
    return CardExpiry(int(match.group(1)), year if year > 99 else 2000 + year)
