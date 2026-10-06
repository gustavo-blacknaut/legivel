import hashlib
import re

import pyotp
import pytest
from fastapi.testclient import TestClient

from legivel.auth import totp
from legivel.auth.routes import REFRESH_COOKIE
from legivel.mail.sender import Mailer, OutgoingMail
from tests.conftest import CSRF_HEADERS, EMAIL, PASSWORD, add_user, login

NEW_PASSWORD = "outra-senha-forte-9"
LINK = re.compile(r"https?://\S+/(convite|verificar-email|redefinir-senha)/([\w-]+)")


class CapturedMailer(Mailer):
    def __init__(self):
        self.sent: list[OutgoingMail] = []

    @property
    def configured(self) -> bool:
        return True

    def send(self, mail: OutgoingMail, sender_name: str) -> None:
        self.sent.append(mail)


@pytest.fixture
def mailbox(bare_client):
    mailer = CapturedMailer()
    bare_client.app.state.mailer = mailer
    return mailer


def token_from(mail: OutgoingMail) -> str:
    match = LINK.search(mail.text)
    assert match, mail.text
    return match.group(2)


def test_setup_creates_first_admin_once(bare_client, mailbox):
    assert bare_client.get("/api/setup").json() == {"required": True}
    assert bare_client.get("/api/public/instance").json()["setup_required"] is True
    response = bare_client.post("/api/setup", json={"email": "Admin@Exemplo.com", "name": "Ana", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    assert response.json()["email_verified"] is False
    assert bare_client.get("/api/auth/me").json()["email"] == "admin@exemplo.com"
    assert len(mailbox.sent) == 1
    assert "Confirme" in mailbox.sent[0].subject
    again = bare_client.post("/api/setup", json={"email": "outra@exemplo.com", "name": "B", "password": PASSWORD})
    assert again.status_code == 409


def test_setup_enforces_password_policy(bare_client):
    response = bare_client.post("/api/setup", json={"email": "a@exemplo.com", "name": "A", "password": "curta"})
    assert response.status_code == 400
    assert bare_client.get("/api/setup").json() == {"required": True}


def test_email_verification_link(bare_client, mailbox):
    bare_client.post("/api/setup", json={"email": "admin@exemplo.com", "name": "Ana", "password": PASSWORD})
    token = token_from(mailbox.sent[0])
    assert bare_client.post("/api/auth/email/verify", json={"token": token}).status_code == 200
    assert bare_client.get("/api/auth/me").json()["email_verified"] is True
    assert bare_client.post("/api/auth/email/verify", json={"token": token}).status_code == 400


def test_invite_flow_creates_account_with_role(client, mailbox):
    login(client)
    created = client.post("/api/users/invitations", json={"email": "revisora@exemplo.com", "role": "reviewer"})
    assert created.status_code == 201
    assert created.json()["emailed"] is True
    token = token_from(mailbox.sent[-1])
    guest = TestClient(client.app, headers=CSRF_HEADERS)
    preview = guest.get(f"/api/auth/invitations/{token}").json()
    assert preview["email"] == "revisora@exemplo.com"
    assert preview["role"] == "reviewer"
    accepted = guest.post(f"/api/auth/invitations/{token}/accept", json={"name": "Rita", "password": NEW_PASSWORD})
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "reviewer"
    assert accepted.json()["email_verified"] is True
    assert guest.get(f"/api/auth/invitations/{token}").status_code == 404
    states = {item["email"]: item["state"] for item in client.get("/api/users/invitations").json()}
    assert states["revisora@exemplo.com"] == "used"


def test_invitation_without_smtp_returns_link(client):
    login(client)
    created = client.post("/api/users/invitations", json={"email": "sem-smtp@exemplo.com", "role": "reader"}).json()
    assert created["emailed"] is False
    assert "/convite/" in created["link"]


def test_invite_can_be_revoked_and_rejects_existing_accounts(client, mailbox):
    login(client)
    duplicate = client.post("/api/users/invitations", json={"email": EMAIL, "role": "reader"})
    assert duplicate.status_code == 400
    invitation = client.post("/api/users/invitations", json={"email": "x@exemplo.com"}).json()["invitation"]
    token = token_from(mailbox.sent[-1])
    assert client.delete(f"/api/users/invitations/{invitation['id']}").status_code == 204
    assert client.get(f"/api/auth/invitations/{token}").status_code == 404


def test_password_reset_flow_revokes_sessions(client, mailbox):
    login(client)
    other = TestClient(client.app, headers=CSRF_HEADERS)
    response = other.post("/api/auth/password/forgot", json={"email": EMAIL})
    assert response.status_code == 202
    assert other.post("/api/auth/password/forgot", json={"email": "ninguem@exemplo.com"}).status_code == 202
    assert len(mailbox.sent) == 1
    token = token_from(mailbox.sent[0])
    assert other.post("/api/auth/password/reset", json={"token": token, "password": "fraca"}).status_code == 400
    assert other.post("/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}).status_code == 200
    assert other.post("/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}).status_code == 400
    client.cookies.delete("legivel_session")
    assert client.post("/api/auth/refresh").status_code == 401
    login(other, EMAIL, NEW_PASSWORD)


def test_admin_reset_link_without_smtp(client):
    target = add_user(client.app, "leitor@exemplo.com", role="reader")
    login(client)
    result = client.post(f"/api/users/{target}/reset-link").json()
    assert result["emailed"] is False
    assert "/redefinir-senha/" in result["link"]


def test_change_password_keeps_current_session_only(client):
    login(client)
    other = TestClient(client.app, headers=CSRF_HEADERS)
    login(other)
    wrong = client.post("/api/auth/password", json={"current_password": "errada", "new_password": NEW_PASSWORD})
    assert wrong.status_code == 400
    changed = client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert changed.json()["revoked_sessions"] == 1
    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401


def test_email_change_requires_confirmation(client, mailbox):
    login(client)
    response = client.post("/api/auth/email", json={"email": "novo@exemplo.com", "password": PASSWORD})
    assert response.json()["emailed"] is True
    assert client.get("/api/auth/me").json()["pending_email"] == "novo@exemplo.com"
    assert client.get("/api/auth/me").json()["email"] == EMAIL
    client.post("/api/auth/email/verify", json={"token": token_from(mailbox.sent[-1])})
    assert client.get("/api/auth/me").json()["email"] == "novo@exemplo.com"


def test_two_factor_setup_login_and_recovery_codes(client):
    login(client)
    setup = client.post("/api/auth/two-factor/setup").json()
    assert setup["qr_svg"].startswith("<svg")
    assert client.post("/api/auth/two-factor/confirm", json={"code": "000000"}).status_code == 400
    code = pyotp.TOTP(setup["secret"]).now()
    codes = client.post("/api/auth/two-factor/confirm", json={"code": code}).json()["recovery_codes"]
    assert len(codes) == 8
    client.post("/api/auth/logout")
    first = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    assert first == {"status": "two_factor", "user": None}
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login/two-factor", json={"code": "123456"}).status_code == 400
    done = client.post("/api/auth/login/two-factor", json={"code": pyotp.TOTP(setup["secret"]).now()})
    assert done.json()["status"] == "ok"
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert client.post("/api/auth/login/two-factor", json={"code": codes[0]}).json()["status"] == "ok"
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert client.post("/api/auth/login/two-factor", json={"code": codes[0]}).status_code == 400


def test_two_factor_can_be_disabled_with_password(client):
    login(client)
    secret = client.post("/api/auth/two-factor/setup").json()["secret"]
    client.post("/api/auth/two-factor/confirm", json={"code": pyotp.TOTP(secret).now()})
    assert client.post("/api/auth/two-factor/disable", json={"password": "errada"}).status_code == 400
    assert client.post("/api/auth/two-factor/disable", json={"password": PASSWORD}).status_code == 204
    assert client.get("/api/auth/me").json()["two_factor_enabled"] is False


def test_single_session_can_be_revoked(client):
    login(client)
    other = TestClient(client.app, headers=CSRF_HEADERS)
    login(other)
    sessions = client.get("/api/auth/sessions").json()
    target = next(item for item in sessions if not item["current"])
    assert client.delete(f"/api/auth/sessions/{target['id']}").status_code == 204
    assert other.get("/api/auth/me").status_code == 401
    assert other.cookies.get(REFRESH_COOKIE)
    assert other.post("/api/auth/refresh").status_code == 401


def test_reader_cannot_upload_or_manage(client):
    add_user(client.app, "leitor@exemplo.com", role="reader")
    login(client, "leitor@exemplo.com")
    assert client.get("/api/people").status_code == 200
    assert client.post("/api/documents").status_code == 403
    assert client.get("/api/users").status_code == 403
    assert client.get("/api/audit").status_code == 403
    assert client.put("/api/settings", json={"values": {"instance_name": "X"}}).status_code == 403


def test_role_permissions_are_configurable(client):
    add_user(client.app, "leitor@exemplo.com", role="reader")
    login(client)
    saved = client.put("/api/settings/roles", json={"role_permissions": {"reader": ["audit.view", "users.manage"]}})
    assert saved.status_code == 200
    assert saved.json()["role_permissions"]["reader"] == ["audit.view", "documents.view"]
    assert client.put("/api/settings/roles", json={"role_permissions": {"admin": []}}).status_code == 400
    client.post("/api/auth/logout")
    login(client, "leitor@exemplo.com")
    assert client.get("/api/audit").status_code == 200
    assert client.get("/api/users").status_code == 403


def test_admin_cannot_demote_last_admin(client):
    login(client)
    me = client.get("/api/auth/me").json()
    assert client.patch(f"/api/users/{me['id']}", json={"role": "reader"}).status_code == 400
    other = add_user(client.app, "outro@exemplo.com", role="reviewer")
    assert client.patch(f"/api/users/{other}", json={"role": "admin"}).json()["role"] == "admin"


def test_account_events_are_audited(client, mailbox):
    login(client)
    client.post("/api/users/invitations", json={"email": "z@exemplo.com"})
    client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    actions = {item["action"] for item in client.get("/api/audit", params={"page_size": 100}).json()["items"]}
    assert {"login", "invite", "password_change"} <= actions


def test_audit_details_carry_no_e_mail_addresses(client, mailbox):
    login(client)
    client.post("/api/users/invitations", json={"email": "convidada@exemplo.com"})
    client.post("/api/auth/login", json={"email": "estranho@exemplo.com", "password": "x"})
    client.post("/api/auth/email", json={"email": "novo@exemplo.com", "password": PASSWORD})
    client.post("/api/scan-links", json={"label": "Maria Souza, admissão"})
    entries = client.get("/api/audit", params={"page_size": 100}).json()["items"]
    texts = " ".join(str(entry["details"]) for entry in entries)
    assert "@" not in texts
    assert "Maria" not in texts


def test_recovery_codes_are_keyed_hashes():
    stored = totp.hash_recovery_code("chave-do-servidor-" * 2, "abcde-12345")
    assert stored.startswith("hmac:")
    assert stored != totp.hash_recovery_code("outra-chave-do-servidor-" * 2, "abcde-12345")
    assert totp.find_recovery_code([stored], "chave-do-servidor-" * 2, "ABCDE12345") == stored
    assert totp.find_recovery_code([stored], "outra-chave-do-servidor-" * 2, "abcde-12345") is None


def test_recovery_codes_saved_before_keyed_hashes_still_work():
    legacy = hashlib.sha256(b"abcde12345").hexdigest()
    assert totp.find_recovery_code([legacy], "chave-do-servidor-" * 2, "abcde-12345") == legacy
