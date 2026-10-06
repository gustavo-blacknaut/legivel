import hashlib
import hmac
import io
import secrets

import pyotp
import segno

RECOVERY_CODE_COUNT = 8
RECOVERY_HASH_PREFIX = "hmac:"
RECOVERY_CONTEXT = b"legivel-recovery-code:"
VALID_WINDOW = 1


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def qr_svg(uri: str) -> str:
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(buffer, kind="svg", scale=5, border=2, xmldecl=False, svgns=True)
    return buffer.getvalue().decode()


def verify_code(secret: str, code: str) -> bool:
    digits = "".join(char for char in code if char.isdigit())
    return len(digits) == 6 and pyotp.TOTP(secret).verify(digits, valid_window=VALID_WINDOW)


def normalize_recovery_code(code: str) -> bytes:
    return code.replace("-", "").strip().lower().encode()


def hash_recovery_code(secret_key: str, code: str) -> str:
    digest = hmac.new(secret_key.encode(), RECOVERY_CONTEXT + normalize_recovery_code(code), hashlib.sha256).hexdigest()
    return RECOVERY_HASH_PREFIX + digest


def legacy_recovery_hash(code: str) -> str:
    return hashlib.sha256(normalize_recovery_code(code)).hexdigest()


def find_recovery_code(stored: list[str], secret_key: str, code: str) -> str | None:
    candidates = (hash_recovery_code(secret_key, code), legacy_recovery_hash(code))
    for item in stored:
        if any(hmac.compare_digest(item, candidate) for candidate in candidates):
            return item
    return None


def new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = secrets.token_hex(5)
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes
