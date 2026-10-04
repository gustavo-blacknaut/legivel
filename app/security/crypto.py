import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_HEADER = b"GOCR1"
NONCE_SIZE = 12
KEY_SIZE = 32


class EncryptionKeyError(ValueError):
    pass


class DecryptionError(ValueError):
    pass


def generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(KEY_SIZE)).decode()


def decode_key(encoded_key: str) -> bytes:
    if not encoded_key:
        raise EncryptionKeyError("GREEN_OCR_ENCRYPTION_KEY não definida")
    try:
        raw_key = base64.urlsafe_b64decode(encoded_key.encode())
    except (ValueError, TypeError) as error:
        raise EncryptionKeyError("Chave de criptografia não está em base64 válido") from error
    if len(raw_key) != KEY_SIZE:
        raise EncryptionKeyError(f"Chave de criptografia deve ter {KEY_SIZE} bytes")
    return raw_key


class FileCipher:
    def __init__(self, encoded_key: str):
        self._aead = AESGCM(decode_key(encoded_key))

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        return FORMAT_HEADER + nonce + self._aead.encrypt(nonce, plaintext, associated_data)

    def decrypt(self, payload: bytes, associated_data: bytes = b"") -> bytes:
        if not payload.startswith(FORMAT_HEADER):
            raise DecryptionError("Arquivo não está no formato criptografado esperado")
        body = payload[len(FORMAT_HEADER):]
        nonce, ciphertext = body[:NONCE_SIZE], body[NONCE_SIZE:]
        try:
            return self._aead.decrypt(nonce, ciphertext, associated_data)
        except InvalidTag as error:
            raise DecryptionError("Falha de integridade ou chave incorreta") from error
