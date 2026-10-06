import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FILE_HEADER = b"IDNT2"
LEGACY_HEADERS = (b"IDNT1", b"GOCR1")
KNOWN_HEADERS = (FILE_HEADER, *LEGACY_HEADERS)
FIELD_PREFIX = "enc2:"
NONCE_SIZE = 12
KEY_SIZE = 32
KEY_ID_SIZE = 4
FIELD_CONTEXT = b"legivel-field"
INDEX_CONTEXT = b"legivel-index"


class EncryptionKeyError(ValueError):
    pass


class DecryptionError(ValueError):
    pass


def generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(KEY_SIZE)).decode()


def decode_key(encoded_key: str) -> bytes:
    if not encoded_key:
        raise EncryptionKeyError("LEGIVEL_ENCRYPTION_KEY não definida")
    try:
        raw_key = base64.urlsafe_b64decode(encoded_key.encode())
    except (ValueError, TypeError) as error:
        raise EncryptionKeyError("Chave de criptografia não está em base64 válido") from error
    if len(raw_key) != KEY_SIZE:
        raise EncryptionKeyError(f"Chave de criptografia deve ter {KEY_SIZE} bytes")
    return raw_key


def key_id(raw_key: bytes) -> bytes:
    return hashlib.sha256(b"legivel-key-id" + raw_key).digest()[:KEY_ID_SIZE]


def is_encrypted(payload: bytes) -> bool:
    return payload.startswith(KNOWN_HEADERS)


class KeyRing:
    def __init__(self, current_key: str, previous_keys: list[str] | tuple[str, ...] = ()):
        raw_keys = [decode_key(current_key), *(decode_key(key) for key in previous_keys if key)]
        self.current_id = key_id(raw_keys[0])
        self._ciphers = {key_id(raw): AESGCM(raw) for raw in raw_keys}
        self.index_key = hmac.new(raw_keys[0], INDEX_CONTEXT, hashlib.sha256).digest()

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self._ciphers[self.current_id].encrypt(nonce, plaintext, associated_data)
        return FILE_HEADER + self.current_id + nonce + ciphertext

    def decrypt(self, payload: bytes, associated_data: bytes = b"") -> bytes:
        if payload.startswith(FILE_HEADER):
            body = payload[len(FILE_HEADER):]
            cipher = self._ciphers.get(body[:KEY_ID_SIZE])
            if cipher is None:
                raise DecryptionError("Arquivo cifrado com uma chave que não está configurada")
            return self._open(cipher, body[KEY_ID_SIZE:], associated_data)
        header = next((item for item in LEGACY_HEADERS if payload.startswith(item)), None)
        if header is None:
            raise DecryptionError("Arquivo não está no formato criptografado esperado")
        for cipher in self._ciphers.values():
            try:
                return self._open(cipher, payload[len(header):], associated_data)
            except DecryptionError:
                continue
        raise DecryptionError("Falha de integridade ou chave incorreta")

    def needs_rotation(self, payload: bytes) -> bool:
        return not payload.startswith(FILE_HEADER + self.current_id)

    @staticmethod
    def _open(cipher: AESGCM, body: bytes, associated_data: bytes) -> bytes:
        try:
            return cipher.decrypt(body[:NONCE_SIZE], body[NONCE_SIZE:], associated_data)
        except InvalidTag as error:
            raise DecryptionError("Falha de integridade ou chave incorreta") from error

    def encrypt_text(self, text: str) -> str:
        return FIELD_PREFIX + base64.urlsafe_b64encode(self.encrypt(text.encode(), FIELD_CONTEXT)).decode()

    def decrypt_text(self, stored: str) -> str:
        if not stored.startswith(FIELD_PREFIX):
            return stored
        return self.decrypt(base64.urlsafe_b64decode(stored[len(FIELD_PREFIX):].encode()), FIELD_CONTEXT).decode()

    def text_needs_rotation(self, stored: str) -> bool:
        if not stored.startswith(FIELD_PREFIX):
            return True
        return self.needs_rotation(base64.urlsafe_b64decode(stored[len(FIELD_PREFIX):].encode()))
