import pytest
from sqlalchemy import func, select, text

from legivel.db.models import AuditLog, Document, User
from legivel.db.session import build_engine, build_session_factory
from legivel.db.transfer import TransferError, copy_database
from tests.conftest import TEST_DATABASE_URL, add_user, login, make_client
from tests.synthetic import encode_jpeg, photograph, render_rg_back

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="defina LEGIVEL_TEST_DATABASE_URL para testar com PostgreSQL")


def test_copies_sqlite_into_postgres(tmp_path, database_url):
    source_url = f"sqlite:///{tmp_path / 'origem.db'}"
    with make_client(tmp_path, source_url) as client:
        add_user(client.app, "admin@exemplo.com")
        login(client, "admin@exemplo.com")
        image = encode_jpeg(photograph(render_rg_back()))
        client.post("/api/documents", files={"back": ("verso.jpg", image, "image/jpeg")})
    counts = {item.table: item.copied for item in copy_database(source_url, database_url)}
    assert counts["users"] == 1
    assert counts["documents"] == 1
    engine = build_engine(database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    with build_session_factory(engine)() as session:
        assert session.scalar(select(func.count(Document.id))) == 1
        assert session.scalar(select(User.email)) == "admin@exemplo.com"
        assert session.scalar(select(func.count(AuditLog.id))) >= 2
        session.add(User(email="nova@exemplo.com", password_hash="x", recovery_codes=[]))
        session.commit()
    engine.dispose()
    with pytest.raises(TransferError, match="já tem dados"):
        copy_database(source_url, database_url)


def test_refuses_outdated_sqlite(tmp_path, database_url):
    source_url = f"sqlite:///{tmp_path / 'vazio.db'}"
    engine = build_engine(source_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE exemplo (id INTEGER)"))
    engine.dispose()
    with pytest.raises(TransferError, match="alembic upgrade head"):
        copy_database(source_url, database_url)
