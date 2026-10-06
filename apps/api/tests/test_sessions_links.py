from datetime import timedelta

from fastapi.testclient import TestClient

from legivel.auth.routes import REFRESH_COOKIE
from legivel.db.base import utc_now
from legivel.db.models import Person, RefreshToken
from tests.conftest import CSRF_HEADERS, login
from tests.synthetic import encode_jpeg, photograph, render_rg_back


def upload(client):
    image = encode_jpeg(photograph(render_rg_back()))
    return client.post("/api/documents", files={"back": ("verso.jpg", image, "image/jpeg")}).json()


def test_login_sets_refresh_cookie_and_refresh_restores_session(client):
    login(client)
    refresh_token = client.cookies.get(REFRESH_COOKIE)
    assert refresh_token
    client.cookies.delete("legivel_session")
    assert client.get("/api/overview").status_code == 401
    restored = client.post("/api/auth/refresh")
    assert restored.status_code == 200
    assert client.get("/api/overview").status_code == 200
    assert client.cookies.get(REFRESH_COOKIE) != refresh_token


def test_reused_refresh_token_revokes_every_session(client):
    login(client)
    stolen = client.cookies.get(REFRESH_COOKIE)
    client.post("/api/auth/refresh")
    rotated = client.cookies.get(REFRESH_COOKIE)
    client.cookies.set(REFRESH_COOKIE, stolen, path="/")
    assert client.post("/api/auth/refresh").status_code == 401
    client.cookies.set(REFRESH_COOKIE, rotated, path="/")
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client):
    login(client)
    token = client.cookies.get(REFRESH_COOKIE)
    client.post("/api/auth/logout")
    client.cookies.set(REFRESH_COOKIE, token, path="/")
    assert client.post("/api/auth/refresh").status_code == 401


def test_sessions_list_and_revoke_others(client):
    login(client)
    other = TestClient(client.app, headers=CSRF_HEADERS)
    login(other)
    listed = client.get("/api/auth/sessions").json()
    assert len(listed) == 2
    assert sum(item["current"] for item in listed) == 1
    assert client.post("/api/auth/sessions/revoke-others").json() == {"revoked": 1}
    other.cookies.delete("legivel_session")
    assert other.post("/api/auth/refresh").status_code == 401


def test_scan_link_flow_is_single_use_and_public(client):
    login(client)
    created = client.post("/api/scan-links", json={"label": "Candidata vaga X", "hours": 24}).json()
    token = created["token"]
    assert created["state"] == "active"

    visitor = TestClient(client.app, headers=CSRF_HEADERS)
    assert visitor.get(f"/api/public/scan/{token}").json()["state"] == "active"
    image = encode_jpeg(photograph(render_rg_back()))
    response = visitor.post(f"/api/public/scan/{token}", files={"back": ("verso.jpg", image, "image/jpeg")})
    assert response.status_code == 201
    assert "MARIANA" not in response.text
    assert visitor.get("/api/overview").status_code == 401

    links = client.get("/api/scan-links").json()
    assert links[0]["state"] == "used"
    assert links[0]["document_id"] is not None
    again = visitor.post(f"/api/public/scan/{token}", files={"back": ("verso.jpg", image, "image/jpeg")})
    assert again.status_code == 410
    assert visitor.get("/api/public/scan/token-invalido").status_code == 404


def test_revoked_link_rejects_uploads(client):
    login(client)
    created = client.post("/api/scan-links", json={}).json()
    assert client.delete(f"/api/scan-links/{created['id']}").status_code == 204
    image = encode_jpeg(photograph(render_rg_back()))
    response = client.post(f"/api/public/scan/{created['token']}", files={"back": ("verso.jpg", image, "image/jpeg")})
    assert response.status_code == 410


def test_person_edit_validates_and_strips_accents(client):
    login(client)
    person_id = upload(client)["person_id"]
    edited = client.put(f"/api/people/{person_id}", json={"values": {"mother_name": "lúcia  helena", "birth_date": "01/02/1990"}})
    assert edited.status_code == 200
    assert edited.json()["mother_name"] == "LUCIA HELENA"
    assert edited.json()["birth_date"] == "01/02/1990"
    assert client.put(f"/api/people/{person_id}", json={"values": {"cpf": "111.111.111-11"}}).status_code == 400
    assert client.put(f"/api/people/{person_id}", json={"values": {"birth_date": "31/02/1990"}}).status_code == 400


def test_verify_person_fixes_accents_and_reports_problems(client):
    login(client)
    person_id = upload(client)["person_id"]
    with client.app_state.session_factory() as session:
        person = session.get(Person, person_id)
        person.mother_name = "LÚCIA HELENA OLIVEIRA"
        person.birthplace = None
        session.commit()
    result = client.post(f"/api/people/{person_id}/verify").json()
    assert result["person"]["mother_name"] == "LUCIA HELENA OLIVEIRA"
    assert result["person"]["birthplace"] == "CAMPINAS-SP"
    assert any("acentos" in change for change in result["changes"])
    assert any("aguardando revisão" in problem for problem in result["problems"])


def test_person_detail_lists_other_data(client):
    login(client)
    person_id = upload(client)["person_id"]
    detail = client.get(f"/api/people/{person_id}").json()
    labels = {item["label"]: item["value"] for item in detail["other_data"]}
    assert labels["Número do RG"] == "48.2**.**5-6"
    assert labels["Órgão expedidor"] == "SSP/SP"
    revealed = client.get(f"/api/people/{person_id}", params={"reveal": "true"}).json()
    assert {item["label"]: item["value"] for item in revealed["other_data"]}["Número do RG"] == "48.217.395-6"


def test_timezone_setting(client):
    login(client)
    assert client.get("/api/settings").json()["values"]["timezone"] == "America/Sao_Paulo"
    saved = client.put("/api/settings", json={"values": {"timezone": "America/Manaus"}}).json()
    assert saved["values"]["timezone"] == "America/Manaus"
    assert client.get("/api/settings").json()["values"]["timezone"] == "America/Manaus"
    assert client.put("/api/settings", json={"values": {"timezone": "Lua/Base"}}).status_code == 400
    assert "America/Recife" in client.get("/api/settings/timezones").json()


def test_audit_records_views_edits_and_ip(client):
    login(client)
    document = upload(client)
    client.get(f"/api/documents/{document['id']}")
    client.get(f"/api/people/{document['person_id']}")
    client.get(document["pages"][0]["original_url"])
    client.put(f"/api/people/{document['person_id']}", json={"values": {"birthplace": "SANTOS-SP"}})
    entries = client.get("/api/audit", params={"page_size": 100}).json()["items"]
    actions = {(entry["action"], entry["entity"]) for entry in entries}
    assert {("view", "document"), ("view", "person"), ("view", "image"), ("update", "person"), ("create", "document")} <= actions
    assert all(entry["ip_address"] for entry in entries)
    update = next(entry for entry in entries if entry["action"] == "update")
    assert update["details"] == "Naturalidade"


def age_session(client, **moments):
    with client.app_state.session_factory() as session:
        for token in session.query(RefreshToken).all():
            for name, value in moments.items():
                setattr(token, name, value)
        session.commit()


def test_idle_session_requires_a_new_login(client):
    login(client)
    age_session(client, created_at=utc_now() - timedelta(hours=13))
    client.cookies.delete("legivel_session")
    assert client.post("/api/auth/refresh").status_code == 401


def test_renewing_does_not_extend_the_absolute_limit(client):
    login(client)
    age_session(client, started_at=utc_now() - timedelta(days=31))
    client.cookies.delete("legivel_session")
    assert client.post("/api/auth/refresh").status_code == 401


def test_renewal_keeps_the_original_start(client):
    login(client)
    with client.app_state.session_factory() as session:
        first = session.query(RefreshToken).one().started_at
    client.cookies.delete("legivel_session")
    assert client.post("/api/auth/refresh").status_code == 200
    with client.app_state.session_factory() as session:
        latest = session.query(RefreshToken).order_by(RefreshToken.id.desc()).first()
        assert latest.started_at == first
