from tests.conftest import add_user, login
from tests.test_data_protection import CPF, upload


def person_id(client) -> int:
    return client.get("/api/people").json()["items"][0]["id"]


def test_export_contains_full_person_data_and_is_audited(client):
    login(client)
    upload(client)
    identifier = person_id(client)
    client.get(f"/api/people/{identifier}")
    response = client.get(f"/api/people/{identifier}/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="pessoa-{identifier}.json"'
    assert response.headers["cache-control"] == "no-store"
    content = response.json()
    assert content["format"] == "legivel.person"
    assert content["person"]["cpf"] == CPF
    document = content["documents"][0]
    assert document["type"] == "rg"
    assert document["fields"]["cpf"] == "529.982.247-25"
    assert document["images"][0]["sha256"]
    assert {"action": "view", "entity": "person", "entity_id": identifier} in [
        {key: entry[key] for key in ("action", "entity", "entity_id")} for entry in content["access_history"]
    ]
    audit = client.get("/api/audit", params={"action": "export"}).json()["items"]
    assert [(entry["entity"], entry["entity_id"]) for entry in audit] == [("person", identifier)]


def test_export_requires_reveal_permission(client):
    login(client)
    upload(client)
    identifier = person_id(client)
    add_user(client.app, "leitura@exemplo.com", role="reader")
    client.post("/api/auth/logout")
    login(client, "leitura@exemplo.com")
    assert client.get(f"/api/people/{identifier}/export").status_code == 403


def test_export_of_missing_person_is_not_found(client):
    login(client)
    assert client.get("/api/people/999/export").status_code == 404
