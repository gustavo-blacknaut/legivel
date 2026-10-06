from datetime import date

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from legivel.db.base import Base
from legivel.db.models import Document, DocumentImage, DocumentType, Person
from legivel.db.session import build_engine, build_session_factory


def upgrade(engine, revision: str = "head") -> None:
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


@pytest.fixture
def raw_engine(database_url):
    engine = build_engine(database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    yield engine
    engine.dispose()


@pytest.fixture
def migrated_engine(raw_engine):
    upgrade(raw_engine)
    return raw_engine


def test_migration_creates_all_tables(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"users", "people", "documents", "document_images", "audit_log", "alembic_version"} <= tables


def test_migration_matches_models(migrated_engine):
    with migrated_engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_downgrade_removes_tables(migrated_engine):
    config = Config("alembic.ini")
    with migrated_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(migrated_engine).get_table_names()) <= {"alembic_version"}


def test_cpf_is_unique_per_person(migrated_engine):
    factory = build_session_factory(migrated_engine)
    with factory() as session:
        session.add_all([Person(cpf="52998224725"), Person(cpf=None), Person(cpf=None)])
        session.commit()
        session.add(Person(cpf="52998224725"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_deleting_person_cascades_to_documents_and_images(migrated_engine):
    factory = build_session_factory(migrated_engine)
    with factory() as session:
        person = Person(cpf="52998224725", full_name="MARIA DA SILVA")
        document = Document(doc_type=DocumentType.CNH, cpf="52998224725", birth_date=date(1985, 5, 10))
        document.images.append(
            DocumentImage(side="front", original_path="originals/aa/x.bin", original_mime="image/jpeg", sha256="0" * 64)
        )
        person.documents.append(document)
        session.add(person)
        session.commit()
        session.delete(person)
        session.commit()
        assert session.query(Document).count() == 0
        assert session.query(DocumentImage).count() == 0


def test_usernames_become_e_mail_accounts(raw_engine):
    upgrade(raw_engine, "0004")
    with raw_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES "
                "('gustavo', 'hash', 'admin', true, CURRENT_TIMESTAMP), "
                "('Ana@Exemplo.com', 'hash', 'operator', true, CURRENT_TIMESTAMP)"
            )
        )
    upgrade(raw_engine)
    with raw_engine.connect() as connection:
        rows = connection.execute(text("SELECT email, name, role FROM users ORDER BY id")).all()
    assert [tuple(row) for row in rows] == [
        ("gustavo@legivel.local", "gustavo", "admin"),
        ("ana@exemplo.com", "Ana@Exemplo.com", "reviewer"),
    ]


def add_audit_entry(connection) -> int:
    user_id = connection.execute(
        text(
            "INSERT INTO users (email, password_hash, role, name, is_active, created_at)"
            " VALUES ('auditoria@exemplo.com', 'x', 'admin', 'Auditoria', true, CURRENT_TIMESTAMP) RETURNING id"
        )
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO audit_log (user_id, action, entity, entity_id, occurred_at)"
            " VALUES (:user_id, 'login', 'user', :user_id, CURRENT_TIMESTAMP)"
        ),
        {"user_id": user_id},
    )
    return user_id


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_log SET action = 'logout'", "UPDATE audit_log SET user_id = NULL, details = 'x'", "DELETE FROM audit_log"],
)
def test_audit_log_rejects_changes(migrated_engine, statement):
    with migrated_engine.begin() as connection:
        add_audit_entry(connection)
    with pytest.raises(Exception, match="append-only"), migrated_engine.begin() as connection:
        connection.execute(text(statement))


def test_deleting_a_user_keeps_the_audit_entries(migrated_engine):
    with migrated_engine.begin() as connection:
        user_id = add_audit_entry(connection)
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
    with migrated_engine.connect() as connection:
        assert connection.execute(text("SELECT user_id, action FROM audit_log")).all() == [(None, "login")]
