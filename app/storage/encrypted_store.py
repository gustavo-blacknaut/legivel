import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.security.crypto import FileCipher

ALLOWED_CATEGORIES = ("originals", "processed", "thumbnails")


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    sha256: str
    size_bytes: int


class EncryptedFileStore:
    def __init__(self, root_dir: Path, cipher: FileCipher):
        self._root = root_dir.resolve()
        self._cipher = cipher

    def save(self, category: str, content: bytes) -> StoredFile:
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Categoria inválida: {category}")
        file_id = uuid.uuid4().hex
        relative_path = f"{category}/{file_id[:2]}/{file_id}.bin"
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._cipher.encrypt(content, relative_path.encode()))
        return StoredFile(relative_path, hashlib.sha256(content).hexdigest(), len(content))

    def load(self, relative_path: str) -> bytes:
        return self._cipher.decrypt(self._resolve(relative_path).read_bytes(), relative_path.encode())

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
