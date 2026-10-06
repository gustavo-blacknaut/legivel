from dataclasses import dataclass
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, func, insert, select, text

from legivel.db import models
from legivel.db.session import build_engine

Base = models.Base
BATCH_SIZE = 500
ALEMBIC_INI = "alembic.ini"


class TransferError(RuntimeError):
    pass


@dataclass(frozen=True)
class TableCount:
    table: str
    copied: int


def head_revision() -> str:
    return ScriptDirectory.from_config(Config(ALEMBIC_INI)).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade(database_url: str) -> None:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


def as_utc(row: dict) -> dict:
    return {
        key: value.replace(tzinfo=UTC) if isinstance(value, datetime) and value.tzinfo is None else value
        for key, value in row.items()
    }


def ensure_empty(engine: Engine) -> None:
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            if connection.scalar(select(func.count()).select_from(table)):
                raise TransferError(f"O banco de destino já tem dados na tabela {table.name}. Use um banco vazio.")


def reset_sequences(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if "id" not in table.c:
                continue
            connection.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
                )
            )


def copy_database(source_url: str, target_url: str) -> list[TableCount]:
    if not source_url.startswith("sqlite"):
        raise TransferError("A origem precisa ser um banco SQLite (sqlite:///caminho.db).")
    if target_url.startswith("postgresql://"):
        target_url = "postgresql+psycopg://" + target_url.removeprefix("postgresql://")
    if not target_url.startswith("postgresql+psycopg://"):
        raise TransferError("O destino precisa ser PostgreSQL (postgresql://usuario:senha@host:5432/banco).")
    source = build_engine(source_url)
    target = build_engine(target_url)
    try:
        if current_revision(source) != head_revision():
            raise TransferError(
                f"O SQLite está na versão {current_revision(source)}; rode 'alembic upgrade head' nele antes de copiar."
            )
        upgrade(target_url)
        ensure_empty(target)
        counts = []
        with source.connect() as reader, target.begin() as writer:
            for table in Base.metadata.sorted_tables:
                total = 0
                result = reader.execute(select(table)).mappings()
                while batch := result.fetchmany(BATCH_SIZE):
                    writer.execute(insert(table), [as_utc(dict(row)) for row in batch])
                    total += len(batch)
                counts.append(TableCount(table.name, total))
        reset_sequences(target)
        with source.connect() as reader, target.connect() as checker:
            for table in Base.metadata.sorted_tables:
                expected = reader.scalar(select(func.count()).select_from(table))
                copied = checker.scalar(select(func.count()).select_from(table))
                if expected != copied:
                    raise TransferError(f"Contagem diferente em {table.name}: {expected} na origem, {copied} no destino.")
        return counts
    finally:
        source.dispose()
        target.dispose()
