"""Password protected, portable snapshots and offline restoration."""

import base64
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import Date, DateTime, MetaData, func, insert, select, text, update

from legivel.db.base import utc_now
from legivel.db.session import build_engine
from legivel.db.transfer import current_revision, head_revision, upgrade
from legivel.storage.file_store import ALLOWED_CATEGORIES

HEADER = b"LEGIVEL-BACKUP-1\0"
MAX_ARCHIVE = 200 * 1024 * 1024
MAX_EXPANDED = 2 * 1024 * 1024 * 1024


def key_for(password: str, salt: bytes) -> bytes:
    if not 12 <= len(password) <= 256:
        raise ValueError("A senha do backup precisa ter de 12 a 256 caracteres.")
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000).derive(password.encode())


def protect(content: bytes, password: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    return HEADER + salt + nonce + AESGCM(key_for(password, salt)).encrypt(nonce, content, HEADER)


def unprotect(content: bytes, password: str) -> bytes:
    if not content.startswith(HEADER) or len(content) > MAX_ARCHIVE:
        raise ValueError("Arquivo de backup inválido ou acima de 200 MB.")
    body = content[len(HEADER) :]
    try:
        return AESGCM(key_for(password, body[:16])).decrypt(body[16:28], body[28:], HEADER)
    except (InvalidTag, ValueError) as error:
        raise ValueError("Senha incorreta ou backup corrompido.") from error


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"bytes": base64.b64encode(value).decode()}
    raise TypeError(type(value).__name__)


def storage_paths(tables: dict, ring) -> set[str]:
    paths = set()
    for name in ("document_images", "record_pages"):
        for row in tables[name]:
            paths.update(row[key] for key in ("original_path", "processed_path", "thumbnail_path") if row.get(key))
    for row in tables["processing_jobs"]:
        raw = row["payload"]
        payload = json.loads(ring.decrypt_text(raw) if ring else raw) if raw else {}
        paths.update(payload.get("paths", []))
    for row in tables["app_settings"]:
        if row["key"] == "logo_path" and row["value"]:
            paths.add(row["value"])
    return paths


def create_backup(settings, password: str) -> bytes:
    engine = build_engine(settings.database_url)
    metadata = MetaData()
    metadata.reflect(engine)
    output = io.BytesIO()
    root = settings.storage_dir.resolve()
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
            elif engine.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN")
            tables = {
                name: [dict(row) for row in connection.execute(select(table)).mappings()]
                for name, table in metadata.tables.items()
            }
            required = storage_paths(tables, settings.key_ring())
            files = {}
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for category in ALLOWED_CATEGORIES:
                    for path in (root / category).rglob("*.bin"):
                        if path.is_symlink() or not path.resolve().is_relative_to(root):
                            raise ValueError("Arquivo de armazenamento fora da pasta permitida.")
                        relative = path.relative_to(root).as_posix()
                        payload = path.read_bytes()
                        files[relative] = hashlib.sha256(payload).hexdigest()
                        archive.writestr("storage/" + relative, payload)
                if required - files.keys():
                    raise ValueError("Há imagens ausentes. Corrija o armazenamento antes de criar o backup.")
                manifest = {
                    "format": 1,
                    "created_at": utc_now().isoformat(),
                    "tables": tables,
                    "files": files,
                    "secrets": {
                        name: getattr(settings, name) for name in ("secret_key", "encryption_key", "encryption_old_keys")
                    },
                }
                archive.writestr("manifest.json", json.dumps(manifest, default=json_value))
        result = protect(output.getvalue(), password)
        if len(result) > MAX_ARCHIVE:
            raise ValueError("Backup acima de 200 MB. Use os scripts de backup do servidor.")
        write_status(settings, {"created_at": manifest["created_at"], "bytes": len(result), "verified_at": None})
        return result
    finally:
        engine.dispose()


def read_backup(content: bytes, password: str) -> tuple[dict, dict[str, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(unprotect(content, password))) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_EXPANDED:
                raise ValueError("Backup expandido acima do permitido.")
            names = archive.namelist()
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise ValueError("Estrutura do backup inválida.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != 1:
                raise ValueError("Versão de backup incompatível.")
            files = {}
            for relative, digest in manifest["files"].items():
                path = PurePosixPath(relative)
                if path.is_absolute() or ".." in path.parts or "\\" in relative or path.parts[0] not in ALLOWED_CATEGORIES:
                    raise ValueError("Caminho inválido no backup.")
                payload = archive.read("storage/" + relative)
                if hashlib.sha256(payload).hexdigest() != digest:
                    raise ValueError("Falha de integridade no backup.")
                files[relative] = payload
            if set(names) != {"manifest.json", *("storage/" + name for name in files)}:
                raise ValueError("Arquivos inesperados no backup.")
            return manifest, files
    except (KeyError, TypeError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise ValueError("Estrutura do backup inválida.") from error


def rows_for(table, rows):
    for source in rows:
        if set(source) != set(table.c.keys()):
            raise ValueError("Colunas do backup incompatíveis com esta versão.")
        row = dict(source)
        for column in table.c:
            value = row[column.name]
            if value is not None and isinstance(column.type, DateTime):
                row[column.name] = datetime.fromisoformat(value)
            elif value is not None and isinstance(column.type, Date):
                row[column.name] = date.fromisoformat(value)
            elif isinstance(value, dict) and set(value) == {"bytes"}:
                row[column.name] = base64.b64decode(value["bytes"])
        yield row


def populate(engine, manifest, replace: bool = False):
    metadata = MetaData()
    metadata.reflect(engine)
    if set(metadata.tables) != set(manifest["tables"]):
        raise ValueError("Schema do backup incompatível. Use a mesma versão do Legível.")
    sqlite_trigger = None
    with engine.begin() as connection:
        if replace:
            if engine.dialect.name == "sqlite":
                sqlite_trigger = connection.scalar(text("SELECT sql FROM sqlite_master WHERE name='audit_log_no_delete'"))
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS audit_log_no_delete")
            else:
                connection.exec_driver_sql("ALTER TABLE audit_log DISABLE TRIGGER audit_log_append_only")
            for table in reversed(metadata.sorted_tables):
                connection.execute(table.delete())
        else:
            # Migrations create the version row; use the snapshot's version below.
            connection.execute(metadata.tables["alembic_version"].delete())
        for table in metadata.sorted_tables:
            rows = list(rows_for(table, manifest["tables"][table.name]))
            for offset in range(0, len(rows), 500):
                connection.execute(insert(table), rows[offset : offset + 500])
        if replace:
            connection.execute(update(metadata.tables["refresh_tokens"]).values(revoked_at=utc_now()))
            connection.execute(
                insert(metadata.tables["audit_log"]).values(
                    id=(connection.scalar(select(func.max(metadata.tables["audit_log"].c.id))) or 0) + 1,
                    user_id=None,
                    action="restore",
                    entity="system",
                    entity_id=None,
                    occurred_at=utc_now(),
                    details="Restauração aplicada no início da API",
                    ip_address=None,
                )
            )
            if sqlite_trigger:
                connection.exec_driver_sql(sqlite_trigger)
            elif engine.dialect.name == "postgresql":
                connection.exec_driver_sql("ALTER TABLE audit_log ENABLE TRIGGER audit_log_append_only")
        if engine.dialect.name == "postgresql":
            for table in metadata.sorted_tables:
                if "id" in table.c:
                    connection.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
                        )
                    )


def verify_backup(settings, content: bytes, password: str) -> tuple[dict, dict[str, bytes]]:
    manifest, files = read_backup(content, password)
    secrets = {name: getattr(settings, name) for name in ("secret_key", "encryption_key", "encryption_old_keys")}
    if manifest.get("secrets") != secrets:
        raise ValueError("As chaves não correspondem ao backup. Recupere as chaves no servidor antes de restaurar.")
    if storage_paths(manifest["tables"], settings.key_ring()) - files.keys():
        raise ValueError("Há arquivos referenciados ausentes no backup.")
    with tempfile.TemporaryDirectory(prefix="legivel-recovery-") as temporary:
        target_url = "sqlite:///" + (Path(temporary) / "recovery.db").as_posix()
        upgrade(target_url)
        engine = build_engine(target_url)
        try:
            populate(engine, manifest)
            with engine.connect() as connection:
                if connection.exec_driver_sql("PRAGMA foreign_key_check").all():
                    raise ValueError("Relações inválidas no backup.")
                if connection.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
                    raise ValueError("Banco de recuperação inválido.")
                version = current_revision(engine)
                if version != head_revision():
                    raise ValueError("Versão do banco incompatível.")
            ring = settings.key_ring()
            if ring:
                from legivel.security.crypto import is_encrypted
                from legivel.security.rotation import PROTECTED

                for model, fields in PROTECTED:
                    for row in manifest["tables"][model.__tablename__]:
                        for field in fields:
                            if row.get(field):
                                ring.decrypt_text(row[field])

                for name, payload in files.items():
                    if is_encrypted(payload):
                        ring.decrypt(payload, name.encode())
        finally:
            engine.dispose()
    return manifest, files


def maintenance_dir(settings) -> Path:
    directory = settings.storage_dir.resolve() / ".maintenance"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_status(settings, value: dict):
    target = maintenance_dir(settings) / "backup-status.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(target)


def backup_status(settings) -> dict:
    target = maintenance_dir(settings) / "backup-status.json"
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}


def stage_restore(settings, manifest: dict, files: dict[str, bytes]):
    # Stage with the installation key; never keep the user's backup password on disk.
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, payload in files.items():
            archive.writestr("storage/" + name, payload)
    target = maintenance_dir(settings) / "restore.pending"
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(protect(output.getvalue(), settings.secret_key))
    temporary.replace(target)


def apply_pending_restore(settings):
    target = maintenance_dir(settings) / "restore.pending"
    if not target.exists():
        return
    manifest, files = verify_backup(settings, target.read_bytes(), settings.secret_key)
    root = settings.storage_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="restore-", dir=maintenance_dir(settings)) as directory:
        staging = Path(directory)
        for name, payload in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        engine = build_engine(settings.database_url)
        moved = []
        try:
            # Keep old images until the database transaction succeeds.
            for category in ALLOWED_CATEGORIES:
                original, saved, replacement = root / category, staging / (category + "-old"), staging / category
                if original.exists():
                    original.rename(saved)
                moved.append((original, saved))
                replacement.mkdir(exist_ok=True)
                replacement.rename(original)
            populate(engine, manifest, replace=True)
        except Exception:
            for original, saved in reversed(moved):
                if original.exists():
                    shutil.rmtree(original)
                if saved.exists():
                    saved.rename(original)
            raise
        finally:
            engine.dispose()
    target.unlink()
    write_status(settings, {"restored_at": utc_now().isoformat(), "verified_at": utc_now().isoformat()})


def recover_keys(backup_path: Path, output: Path, password: str):
    """Recover configuration files on a replacement server, without printing secrets."""
    manifest, _ = read_backup(backup_path.read_bytes(), password)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / f"{name}.txt").exists() for name in ("secret_key", "encryption_key", "encryption_old_keys")):
        raise FileExistsError("A pasta já contém arquivos de chave. Escolha uma pasta vazia.")
    for name in ("secret_key", "encryption_key", "encryption_old_keys"):
        value = manifest["secrets"][name]
        if not value:
            continue
        target = output / f"{name}.txt"
        with target.open("x", encoding="utf-8") as file:
            os.chmod(target, 0o600)
            file.write(value + "\n")


if __name__ == "__main__":
    import argparse
    import getpass

    parser = argparse.ArgumentParser(description="Recupera as chaves de um backup cifrado em um servidor novo.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    recover_keys(arguments.backup, arguments.output, getpass.getpass("Senha do backup: "))
    print("Chaves recuperadas. Configure os arquivos de segredo antes de iniciar o Legível.")
