import pytest
from fastapi.testclient import TestClient

from legivel.config import ConfigurationError, get_settings, load_settings
from legivel.main import create_app
from legivel.security.crypto import generate_key


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_refuses_to_start_without_encryption_key(monkeypatch):
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    with pytest.raises(ConfigurationError) as error:
        load_settings(_env_file=None)
    assert "LEGIVEL_ENCRYPTION_KEY" in str(error.value)


def test_encryption_can_be_disabled(monkeypatch):
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_ENABLED", "false")
    assert load_settings(_env_file=None).encryption_enabled is False


def test_refuses_short_secret_key_with_variable_name(monkeypatch):
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", "short")
    with pytest.raises(ConfigurationError) as error:
        load_settings(_env_file=None)
    assert "LEGIVEL_SECRET_KEY" in str(error.value)


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("LEGIVEL_DATABASE_URL", "mysql://x", "LEGIVEL_DATABASE_URL"),
        ("LEGIVEL_UPLOAD_FORMATS", "jpeg,gif", "LEGIVEL_UPLOAD_FORMATS"),
        ("LEGIVEL_OCR_DEVICE", "tpu", "LEGIVEL_OCR_DEVICE"),
        ("LEGIVEL_UPLOAD_MAX_MB", "0", "LEGIVEL_UPLOAD_MAX_MB"),
        ("LEGIVEL_PUBLIC_URL", "legivel.local", "LEGIVEL_PUBLIC_URL"),
        ("LEGIVEL_SMTP_HOST", "smtp.exemplo.com", "LEGIVEL_SMTP_FROM"),
    ],
)
def test_invalid_values_are_reported_by_variable(monkeypatch, name, value, expected):
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError) as error:
        load_settings(_env_file=None)
    assert expected in str(error.value)


def test_postgres_url_uses_psycopg(monkeypatch):
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_DATABASE_URL", "postgresql://legivel:senha@db:5432/legivel")
    assert load_settings(_env_file=None).database_url.startswith("postgresql+psycopg://")


def test_health_endpoint_is_public(monkeypatch, tmp_path):
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_DATABASE_URL", f"sqlite:///{tmp_path / 'health.db'}")
    response = TestClient(create_app(load_settings(_env_file=None))).get("/health")
    assert response.json() == {"status": "ok"}


def test_api_does_not_serve_frontend(client):
    assert client.get("/").status_code == 404
    assert client.get("/pessoas").status_code == 404


def test_secrets_can_come_from_files(monkeypatch, tmp_path):
    secret_key = tmp_path / "secret_key"
    encryption_key = tmp_path / "encryption_key"
    database_password = tmp_path / "database_password"
    secret_key.write_text(generate_key() + "\n", encoding="utf-8")
    encryption_key.write_text(generate_key(), encoding="utf-8")
    database_password.write_text("p@ss/word:1", encoding="utf-8")
    monkeypatch.setenv("LEGIVEL_SECRET_KEY_FILE", str(secret_key))
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY_FILE", str(encryption_key))
    monkeypatch.setenv("LEGIVEL_DATABASE_PASSWORD_FILE", str(database_password))
    monkeypatch.setenv("LEGIVEL_DATABASE_URL", "postgresql://legivel_app@db:5432/legivel")
    settings = load_settings(_env_file=None)
    assert settings.secret_key == secret_key.read_text(encoding="utf-8").strip()
    assert settings.database_url == "postgresql+psycopg://legivel_app:p%40ss%2Fword%3A1@db:5432/legivel"


def test_variable_wins_over_secret_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "secret_key"
    secret_file.write_text(generate_key(), encoding="utf-8")
    secret_key = generate_key()
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", secret_key)
    monkeypatch.setenv("LEGIVEL_SECRET_KEY_FILE", str(secret_file))
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    assert load_settings(_env_file=None).secret_key == secret_key


def test_missing_secret_file_names_the_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("LEGIVEL_SECRET_KEY_FILE", str(tmp_path / "ausente"))
    with pytest.raises(ConfigurationError) as error:
        load_settings(_env_file=None)
    assert "LEGIVEL_SECRET_KEY_FILE" in str(error.value)


def test_validation_errors_do_not_echo_the_submitted_values(client):
    secret = "senha-super-secreta-123"
    response = client.post("/api/auth/login", json={"email": 12345, "password": secret, "extra": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert "12345" not in response.text
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_production_refuses_insecure_settings(monkeypatch):
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_PRODUCTION", "true")
    monkeypatch.setenv("LEGIVEL_PUBLIC_URL", "http://192.168.0.10:8091")
    with pytest.raises(ConfigurationError) as error:
        load_settings(_env_file=None)
    assert "LEGIVEL_SECURE_COOKIES=true" in str(error.value)
    assert "https://" in str(error.value)


def test_production_accepts_secure_settings(monkeypatch):
    monkeypatch.setenv("LEGIVEL_ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_SECRET_KEY", generate_key())
    monkeypatch.setenv("LEGIVEL_PRODUCTION", "true")
    monkeypatch.setenv("LEGIVEL_SECURE_COOKIES", "true")
    monkeypatch.setenv("LEGIVEL_PUBLIC_URL", "https://legivel.exemplo.com.br")
    assert load_settings(_env_file=None).production is True
