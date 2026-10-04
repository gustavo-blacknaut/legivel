from app.validators.cpf import only_digits

VOTER_ID_LENGTH = 12
CERTIFICATE_LENGTH = 32
STATE_CODES = {
    "01": "SP",
    "02": "MG",
    "03": "RJ",
    "04": "RS",
    "05": "BA",
    "06": "PR",
    "07": "CE",
    "08": "PE",
    "09": "SC",
    "10": "GO",
    "11": "MA",
    "12": "PB",
    "13": "PA",
    "14": "ES",
    "15": "PI",
    "16": "RN",
    "17": "AL",
    "18": "MT",
    "19": "MS",
    "20": "DF",
    "21": "SE",
    "22": "AM",
    "23": "RO",
    "24": "AC",
    "25": "AP",
    "26": "RR",
    "27": "TO",
    "28": "Exterior",
}


def voter_id_check_digits(sequence: str, state: str) -> str:
    first_total = sum(int(digit) * weight for digit, weight in zip(sequence, range(2, 10), strict=False))
    first = first_total % 11
    if first == 10:
        first = 0
    if first == 0 and state in ("01", "02"):
        first = 1
    second_total = int(state[0]) * 7 + int(state[1]) * 8 + first * 9
    second = second_total % 11
    if second == 10:
        second = 0
    if second == 0 and state in ("01", "02"):
        second = 1
    return f"{first}{second}"


def is_valid_voter_id(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != VOTER_ID_LENGTH:
        return False
    state = digits[8:10]
    if state not in STATE_CODES:
        return False
    return voter_id_check_digits(digits[:8], state) == digits[10:]


def voter_id_state(value: str) -> str | None:
    digits = only_digits(value)
    return STATE_CODES.get(digits[8:10]) if len(digits) == VOTER_ID_LENGTH else None


CERTIFICATE_KINDS = {"1": "Nascimento", "2": "Casamento", "3": "Casamento religioso com efeito civil", "4": "Óbito"}


def certificate_kind(value: str) -> str | None:
    digits = only_digits(value)
    return CERTIFICATE_KINDS.get(digits[14]) if len(digits) == CERTIFICATE_LENGTH else None


def format_certificate_number(value: str) -> str:
    digits = only_digits(value)
    if len(digits) != CERTIFICATE_LENGTH:
        return value
    parts = (
        digits[0:6],
        digits[6:8],
        digits[8:10],
        digits[10:14],
        digits[14],
        digits[15:20],
        digits[20:23],
        digits[23:30],
        digits[30:32],
    )
    return " ".join(parts)


def is_plausible_certificate_number(value: str) -> bool:
    digits = only_digits(value)
    return len(digits) == CERTIFICATE_LENGTH and digits[14] in CERTIFICATE_KINDS and digits[10:14].startswith(("19", "20"))
