import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.auth.users import create_user
from app.config import Settings
from app.main import create_app
from app.security.crypto import generate_key
from tests.synthetic import rg_back_boxes


class FakeEngine:
    name = "fake"

    def read(self, image_bgr):
        return rg_back_boxes()


USERNAME = "operador"
CSRF_HEADERS = {"X-Requested-With": "lince"}
PASSWORD = "senha-de-teste-123"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'web.db'}",
        storage_dir=tmp_path / "storage",
        encryption_key=generate_key(),
        secret_key=generate_key(),
        frontend_dir=tmp_path / "frontend",
    )
    application = create_app(settings)
    config = Config("alembic.ini")
    config.attributes["database_url"] = settings.database_url
    command.upgrade(config, "head")
    with application.state.session_factory() as session:
        create_user(session, USERNAME, PASSWORD)
    application.state.ocr_engine = FakeEngine()
    with TestClient(application, headers=CSRF_HEADERS) as test_client:
        test_client.app_state = application.state
        yield test_client


def login(client):
    response = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    return response
