from functools import lru_cache
from importlib import resources

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MAXIMUM_PASSWORD_LENGTH = 256
DUMMY_PASSWORD = "dummy-password-for-timing"
_state: dict[str, object] = {}


class WeakPasswordError(ValueError):
    pass


def configure_hashing(time_cost: int, memory_kib: int, parallelism: int) -> None:
    hasher = PasswordHasher(time_cost=time_cost, memory_cost=memory_kib, parallelism=parallelism)
    _state["hasher"] = hasher
    _state["dummy_hash"] = hasher.hash(DUMMY_PASSWORD)


def current_hasher() -> PasswordHasher:
    if "hasher" not in _state:
        default = PasswordHasher()
        configure_hashing(default.time_cost, default.memory_cost, default.parallelism)
    return _state["hasher"]


def hash_password(password: str) -> str:
    return current_hasher().hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    hasher = current_hasher()
    try:
        return hasher.verify(password_hash or str(_state["dummy_hash"]), password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return current_hasher().check_needs_rehash(password_hash)


def check_password_policy(password: str, minimum_length: int, require_mixed: bool, email: str = "") -> None:
    if len(password) < minimum_length:
        raise WeakPasswordError(f"A senha precisa ter pelo menos {minimum_length} caracteres.")
    if len(password) > MAXIMUM_PASSWORD_LENGTH:
        raise WeakPasswordError(f"A senha pode ter no máximo {MAXIMUM_PASSWORD_LENGTH} caracteres.")
    if require_mixed and not (any(char.isalpha() for char in password) and any(not char.isalpha() for char in password)):
        raise WeakPasswordError("A senha precisa misturar letras com números ou símbolos.")
    if password.lower() in common_passwords():
        raise WeakPasswordError("Esta senha aparece em listas de senhas vazadas. Escolha outra.")
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in password.lower():
        raise WeakPasswordError("A senha não pode conter o seu e-mail.")


@lru_cache
def common_passwords() -> frozenset[str]:
    text = resources.files("legivel.auth").joinpath("data/common-passwords.txt").read_text(encoding="utf-8")
    return frozenset(line.strip() for line in text.splitlines() if line.strip())
