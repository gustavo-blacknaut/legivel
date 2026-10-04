from datetime import date

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import Document, DocumentImage, DocumentType, Person
from app.db.session import build_engine, build_session_factory


@pytest.fixture
def migrated_engine(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


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
