MASK = "*"
KEEP_START = 3
KEEP_END = 2
MIN_DIGITS = 4
PLAIN_KINDS = frozenset({"date", "parent"})
PLAIN_FIELDS = frozenset({"full_name", "birthplace", "issuing_authority", "cnh_category", "blood_type", "issuing_state"})


def is_sensitive(name: str, kind: str = "text") -> bool:
    return kind == "cpf" or (kind not in PLAIN_KINDS and name not in PLAIN_FIELDS)


def mask_number(value: str | None) -> str | None:
    if not value:
        return value
    positions = [index for index, char in enumerate(value) if char.isdigit()]
    if len(positions) < MIN_DIGITS:
        return value
    hidden = set(positions[KEEP_START:-KEEP_END])
    return "".join(MASK if index in hidden else char for index, char in enumerate(value))


def is_masked(value: str | None) -> bool:
    return bool(value) and MASK in value
