import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from legivel.auth.accounts import create_user
from legivel.config import Settings
from legivel.main import create_app
from legivel.security.crypto import generate_key
from legivel.services.settings import load_runtime
from tests.synthetic import rg_back_boxes

TEST_DATABASE_URL = os.environ.get("LEGIVEL_TEST_DATABASE_URL", "")
EMAIL = "operador@exemplo.com.br"
PASSWORD = "senha-de-teste-123"
CSRF_HEADERS = {"X-Requested-With": "legivel"}


class FakeEngine:
    name = "fake"

    def read(self, image_bgr):
        return rg_back_boxes()


def reset_postgres(url: str) -> None:
    engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


@pytest.fixture
def database_url(tmp_path):
    if TEST_DATABASE_URL:
        reset_postgres(TEST_DATABASE_URL)
        return TEST_DATABASE_URL
    return f"sqlite:///{tmp_path / 'test.db'}"


def migrate(database_url: str) -> None:
    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


def build_settings(tmp_path, database_url: str, **overrides) -> Settings:
    values = {
        "database_url": database_url,
        "storage_dir": tmp_path / "storage",
        "encryption_key": generate_key(),
        "secret_key": generate_key(),
        "ocr_warmup": False,
        "background_jobs": False,
        "_env_file": None,
        **overrides,
    }
    return Settings(**values)


def add_user(application, email: str, password: str = PASSWORD, role: str = "admin", name: str = "") -> int:
    with application.state.session_factory() as session:
        runtime = load_runtime(session, application.state.settings)
        user = create_user(session, email, password, runtime, role, name or email.split("@")[0])
        session.commit()
        return user.id


def make_client(tmp_path, database_url: str, **overrides) -> TestClient:
    settings = build_settings(tmp_path, database_url, **overrides)
    application = create_app(settings)
    migrate(settings.database_url)
    application.state.ocr_engine = FakeEngine()
    test_client = TestClient(application, headers=CSRF_HEADERS)
    test_client.app_state = application.state
    return test_client


@pytest.fixture
def bare_client(tmp_path, database_url):
    with make_client(tmp_path, database_url) as test_client:
        yield test_client


@pytest.fixture
def client(bare_client):
    add_user(bare_client.app, EMAIL, role="admin", name="Operador")
    return bare_client


def login(client, email: str = EMAIL, password: str = PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"
    return response


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("LEGIVEL_") and name != "LEGIVEL_TEST_DATABASE_URL":
            monkeypatch.delenv(name)
    monkeypatch.setenv("LEGIVEL_OCR_WARMUP", "false")
    monkeypatch.setenv("LEGIVEL_BACKGROUND_JOBS", "false")
