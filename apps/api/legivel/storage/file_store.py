import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from legivel.security.crypto import DecryptionError, KeyRing, is_encrypted

ALLOWED_CATEGORIES = ("originals", "processed", "thumbnails", "branding")


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    sha256: str
    size_bytes: int


class FileStore:
    def __init__(self, root_dir: Path, cipher: KeyRing | None):
        self._root = root_dir.resolve()
        self._cipher = cipher

    @property
    def encrypted(self) -> bool:
        return self._cipher is not None

    def save(self, category: str, content: bytes) -> StoredFile:
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Categoria inválida: {category}")
        file_id = uuid.uuid4().hex
        relative_path = f"{category}/{file_id[:2]}/{file_id}.bin"
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self._cipher.encrypt(content, relative_path.encode()) if self._cipher else content
        target.write_bytes(payload)
        return StoredFile(relative_path, hashlib.sha256(content).hexdigest(), len(content))

    def load(self, relative_path: str) -> bytes:
        payload = self._resolve(relative_path).read_bytes()
        if not is_encrypted(payload):
            return payload
        if self._cipher is None:
            raise DecryptionError("Arquivo criptografado, mas LEGIVEL_ENCRYPTION_KEY não está configurada")
        return self._cipher.decrypt(payload, relative_path.encode())

    def rewrite(self, relative_path: str) -> bool:
        target = self._resolve(relative_path)
        if self._cipher is None or not target.exists():
            return False
        payload = target.read_bytes()
        if is_encrypted(payload) and not self._cipher.needs_rotation(payload):
            return False
        content = self.load(relative_path)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(self._cipher.encrypt(content, relative_path.encode()))
        temporary.replace(target)
        return True

    def delete(self, relative_path: str) -> bool:
        target = self._resolve(relative_path)
        if not target.exists():
            return False
        target.unlink()
        return True

    def _resolve(self, relative_path: str) -> Path:
        target = (self._root / relative_path).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("Caminho fora do diretório de armazenamento")
        return target
