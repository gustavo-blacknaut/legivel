import hashlib
import hmac
import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from legivel.security.crypto import FIELD_PREFIX, KeyRing

_state: dict[str, object] = {"ring": None, "index_key": hashlib.sha256(b"legivel-index-unconfigured").digest()}


def configure_fields(ring: KeyRing | None, secret_key: str) -> None:
    _state["ring"] = ring
    _state["index_key"] = ring.index_key if ring else hmac.new(secret_key.encode(), b"legivel-index", hashlib.sha256).digest()


def current_ring() -> KeyRing | None:
    ring = _state["ring"]
    return ring if isinstance(ring, KeyRing) else None


def protect(text: str) -> str:
    ring = current_ring()
    return ring.encrypt_text(text) if ring else text


def reveal(stored: str) -> str:
    if not stored.startswith(FIELD_PREFIX):
        return stored
    ring = current_ring()
    if ring is None:
        raise ValueError("Campo cifrado, mas LEGIVEL_ENCRYPTION_KEY não está configurada")
    return ring.decrypt_text(stored)


def blind_index(value: str | None) -> str | None:
    if not value:
        return None
    return hmac.new(bytes(_state["index_key"]), value.encode(), hashlib.sha256).hexdigest()


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else protect(str(value))

    def process_result_value(self, value, dialect):
        return None if value is None else reveal(value)


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else protect(json.dumps(value, ensure_ascii=False))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, dict | list):
            return value
        return json.loads(reveal(value))
