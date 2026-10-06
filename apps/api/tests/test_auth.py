import pytest
from sqlalchemy import select

from legivel.auth.passwords import (
    WeakPasswordError,
    check_password_policy,
    configure_hashing,
    hash_password,
    needs_rehash,
    verify_password,
)
from legivel.auth.throttle import LoginThrottle
from legivel.db.models import User
from tests.conftest import EMAIL, PASSWORD, add_user, login


def test_password_hash_round_trip():
    password_hash = hash_password("uma-senha-forte-1")
    assert password_hash.startswith("$argon2")
    assert verify_password(password_hash, "uma-senha-forte-1")
    assert not verify_password(password_hash, "outra-senha")
    assert not verify_password(None, "qualquer")


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("curta1", "pelo menos"),
        ("somenteletrasaqui", "misturar"),
        ("maria.souza-2024", "e-mail"),
        ("1Q2W3E4R5T", "vazadas"),
    ],
)
def test_password_policy(password, message):
    with pytest.raises(WeakPasswordError, match=message):
        check_password_policy(password, 10, True, "maria.souza@exemplo.com")


def test_throttle_blocks_after_limit():
    throttle = LoginThrottle(max_attempts=3, window_seconds=60)
    for _ in range(3):
        throttle.record_failure("ip:user")
    assert throttle.is_blocked("ip:user")
    throttle.reset("ip:user")
    assert not throttle.is_blocked("ip:user")


@pytest.mark.parametrize(
    "path", ["/api/overview", "/api/people", "/api/documents/1", "/api/images/1/original", "/api/users", "/api/auth/me"]
)
def test_api_requires_login(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/documents"),
        ("delete", "/api/documents/1"),
        ("delete", "/api/people/1"),
        ("post", "/api/documents/1/reprocess"),
        ("post", "/api/users/invitations"),
    ],
)
def test_mutations_are_rejected_when_anonymous(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_mutations_without_csrf_header_are_refused(client):
    login(client)
    response = client.delete("/api/documents/1", headers={"X-Requested-With": ""})
    assert response.status_code == 403


def test_wrong_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": "senha-errada"})
    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]


def test_login_does_not_reveal_whether_the_account_exists(client):
    known = client.post("/api/auth/login", json={"email": EMAIL, "password": "senha-errada"})
    unknown = client.post("/api/auth/login", json={"email": "ninguem@exemplo.com", "password": "senha-errada"})
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()


def test_email_is_case_insensitive(client):
    response = client.post("/api/auth/login", json={"email": EMAIL.upper(), "password": PASSWORD})
    assert response.json()["user"]["email"] == EMAIL


def test_login_me_and_logout(client):
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    me = client.get("/api/auth/me").json()
    assert me["email"] == EMAIL
    assert me["role"] == "admin"
    assert "users.manage" in me["permissions"]
    assert client.get("/api/overview").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/overview").status_code == 401


def test_account_is_locked_after_repeated_failures(client):
    for _ in range(4):
        assert client.post("/api/auth/login", json={"email": EMAIL, "password": "errada"}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": EMAIL, "password": "errada"})
    assert locked.status_code == 401
    blocked = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert blocked.status_code == 401
    assert blocked.json() == locked.json()
    add_user(client.app, "auditora@exemplo.com.br")
    login(client, "auditora@exemplo.com.br")
    actions = {item["action"] for item in client.get("/api/audit").json()["items"]}
    assert {"lock", "login_failed"} <= actions


def test_admin_can_unlock_account(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": EMAIL, "password": "errada"})
    add_user(client.app, "chefe@exemplo.com.br")
    login(client, "chefe@exemplo.com.br")
    accounts = {item["email"]: item for item in client.get("/api/users").json()}
    assert accounts[EMAIL]["locked"]
    assert client.patch(f"/api/users/{accounts[EMAIL]['id']}", json={"unlock": True}).json()["locked"] is False
    client.post("/api/auth/logout")
    login(client)


def test_ip_is_throttled_across_accounts(client):
    for index in range(20):
        client.post("/api/auth/login", json={"email": f"pessoa{index}@exemplo.com", "password": "errada"})
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 429


def test_session_cookies_are_strict_and_http_only(client):
    cookies = [value.lower() for value in login(client).headers.get_list("set-cookie")]
    assert len(cookies) == 2
    for cookie in cookies:
        assert "httponly" in cookie
        assert "samesite=strict" in cookie


def test_disabled_account_cannot_log_in(client):
    user_id = add_user(client.app, "leitora@exemplo.com.br", role="reader")
    login(client)
    assert client.patch(f"/api/users/{user_id}", json={"is_active": False}).status_code == 200
    client.post("/api/auth/logout")
    response = client.post("/api/auth/login", json={"email": "leitora@exemplo.com.br", "password": PASSWORD})
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/public/scan/{token}", None),
        ("post", "/api/auth/email/verify", {"token": "{token}"}),
        ("post", "/api/auth/invitations/{token}/accept", {"name": "Pessoa", "password": "senha-boa-12345"}),
    ],
)
def test_token_guessing_is_throttled(client, method, path, payload):
    def attempt(index: int):
        token = f"token-invalido-{index}"
        body = {key: value.format(token=token) for key, value in payload.items()} if payload else None
        return client.request(method.upper(), path.format(token=token), json=body)

    statuses = {attempt(index).status_code for index in range(20)}
    assert 429 not in statuses
    assert attempt(20).status_code == 429


def test_login_upgrades_hashes_made_with_old_parameters(client):
    configure_hashing(2, 19456, 1)
    old_hash = hash_password(PASSWORD)
    configure_hashing(3, 65536, 4)
    assert "m=19456,t=2,p=1" in old_hash
    assert needs_rehash(old_hash)
    with client.app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.email == EMAIL))
        user.password_hash = old_hash
        session.commit()
    login(client)
    with client.app.state.session_factory() as session:
        upgraded = session.scalar(select(User).where(User.email == EMAIL)).password_hash
    assert "m=65536,t=3,p=4" in upgraded
    assert verify_password(upgraded, PASSWORD)
