import re

CPF_LENGTH = 11


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def calculate_check_digits(first_nine_digits: str) -> str:
    digits = [int(char) for char in first_nine_digits]
    for weight_start in (10, 11):
        total = sum(digit * weight for digit, weight in zip(digits, range(weight_start, 1, -1), strict=False))
        remainder = (total * 10) % 11
        digits.append(0 if remainder == 10 else remainder)
    return f"{digits[-2]}{digits[-1]}"


def is_valid_cpf(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != CPF_LENGTH or len(set(digits)) == 1:
        return False
    return calculate_check_digits(digits[:9]) == digits[9:]


def normalize_cpf(value: str) -> str | None:
    digits = only_digits(value)
    return digits if is_valid_cpf(digits) else None


def format_cpf(value: str) -> str:
    digits = only_digits(value)
    if len(digits) != CPF_LENGTH:
        return value
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
