import pytest

from app.auth.passwords import hash_password, verify_password
from app.auth.throttle import LoginThrottle
from tests.conftest import PASSWORD, USERNAME, login


def test_password_hash_round_trip():
    password_hash = hash_password("uma-senha-forte")
    assert password_hash.startswith("$argon2")
    assert verify_password(password_hash, "uma-senha-forte")
    assert not verify_password(password_hash, "outra-senha")
    assert not verify_password(None, "qualquer")


def test_throttle_blocks_after_limit():
    throttle = LoginThrottle(max_attempts=3, window_seconds=60)
    for _ in range(3):
        throttle.record_failure("ip:user")
    assert throttle.is_blocked("ip:user")
    throttle.reset("ip:user")
    assert not throttle.is_blocked("ip:user")


@pytest.mark.parametrize("path", ["/api/overview", "/api/people", "/api/documents/1", "/api/images/1/original"])
def test_api_requires_login(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/documents"),
        ("delete", "/api/documents/1"),
        ("delete", "/api/people/1"),
        ("post", "/api/documents/1/reprocess"),
    ],
)
def test_mutations_are_rejected_when_anonymous(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_mutations_without_csrf_header_are_refused(client):
    login(client)
    response = client.delete("/api/documents/1", headers={"X-Requested-With": ""})
    assert response.status_code == 403


def test_wrong_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"username": USERNAME, "password": "senha-errada"})
    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]


def test_login_me_and_logout(client):
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    assert client.get("/api/auth/me").json()["username"] == USERNAME
    assert client.get("/api/overview").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/overview").status_code == 401


def test_login_is_throttled(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": USERNAME, "password": "senha-errada"})
    response = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 429


def test_session_cookie_is_strict_and_http_only(client):
    cookie = login(client).headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
