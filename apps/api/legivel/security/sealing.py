import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_SIZE = 12
CONTEXT = b"legivel-sealed-v1"


class SealError(ValueError):
    pass


def derive_key(secret_key: str) -> bytes:
    return hashlib.sha256(CONTEXT + secret_key.encode()).digest()


def seal(secret_key: str, plaintext: str) -> str:
    nonce = os.urandom(NONCE_SIZE)
    payload = nonce + AESGCM(derive_key(secret_key)).encrypt(nonce, plaintext.encode(), CONTEXT)
    return base64.urlsafe_b64encode(payload).decode()


def unseal(secret_key: str, sealed: str) -> str:
    try:
        payload = base64.urlsafe_b64decode(sealed.encode())
        return AESGCM(derive_key(secret_key)).decrypt(payload[:NONCE_SIZE], payload[NONCE_SIZE:], CONTEXT).decode()
    except (InvalidTag, ValueError) as error:
        raise SealError("Não foi possível abrir o segredo com a LEGIVEL_SECRET_KEY atual") from error
