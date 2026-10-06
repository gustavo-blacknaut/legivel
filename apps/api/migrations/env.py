from alembic import context

from legivel.config import get_settings
from legivel.db import models
from legivel.db.session import build_engine

target_metadata = models.Base.metadata


def resolve_database_url() -> str:
    return context.config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=resolve_database_url(), target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = build_engine(resolve_database_url())
    with engine.connect() as new_connection:
        context.configure(connection=new_connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
