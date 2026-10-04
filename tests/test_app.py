import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import MissingSecretKeyError, create_app
from app.security.crypto import EncryptionKeyError, generate_key


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_app_refuses_to_start_without_encryption_key(monkeypatch):
    monkeypatch.setenv("LINCE_ENCRYPTION_KEY", "")
    with pytest.raises(EncryptionKeyError):
        create_app()


def test_app_refuses_to_start_without_secret_key(monkeypatch):
    monkeypatch.setenv("LINCE_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LINCE_SECRET_KEY", "short")
    with pytest.raises(MissingSecretKeyError):
        create_app()


def test_health_endpoint_is_public(monkeypatch):
    monkeypatch.setenv("LINCE_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LINCE_SECRET_KEY", generate_key())
    response = TestClient(create_app()).get("/health")
    assert response.json() == {"status": "ok"}


def test_serves_single_page_app_with_client_side_routes(monkeypatch, tmp_path):
    frontend = tmp_path / "dist"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (frontend / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (frontend / "logo.png").write_bytes(b"png")
    monkeypatch.setenv("LINCE_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LINCE_SECRET_KEY", generate_key())
    monkeypatch.setenv("LINCE_FRONTEND_DIR", str(frontend))
    client = TestClient(create_app())
    assert "id=root" in client.get("/documentos/5").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/logo.png").content == b"png"
    assert client.get("/../../etc/passwd").status_code in (200, 404)
    assert "root:" not in client.get("/../../etc/passwd").text
    assert client.get("/api/overview").status_code == 401
