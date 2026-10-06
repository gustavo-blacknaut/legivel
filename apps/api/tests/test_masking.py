import pytest

from legivel.db.models import Person
from legivel.security.masking import is_masked, is_sensitive, mask_number
from tests.conftest import PASSWORD, add_user, login
from tests.synthetic import encode_jpeg, photograph, render_rg_back


def upload(client):
    image = encode_jpeg(photograph(render_rg_back()))
    return client.post("/api/documents", files={"back": ("verso.jpg", image, "image/jpeg")}).json()


def values_of(detail):
    return {field["name"]: field["value"] for field in detail["fields"]}


@pytest.mark.parametrize(
    ("value", "masked"),
    [
        ("529.982.247-25", "529.***.***-25"),
        ("52998224725", "529******25"),
        ("MG-12.345.678", "MG-12.3**.*78"),
        ("SSP", "SSP"),
        ("12", "12"),
        (None, None),
    ],
)
def test_mask_number(value, masked):
    assert mask_number(value) == masked


def test_only_identifiers_are_sensitive():
    assert is_sensitive("cpf", "cpf")
    assert is_sensitive("rg_number")
    assert is_sensitive("health_card", "extra")
    assert not is_sensitive("full_name")
    assert not is_sensitive("birth_date", "date")
    assert not is_sensitive("mother_name", "parent")
    assert is_masked("529.***") and not is_masked("529.982")


def test_lists_and_details_are_masked_by_default(client):
    login(client)
    document = upload(client)
    person = client.get("/api/people").json()["items"][0]
    assert person["cpf"] == "529.***.***-25"
    assert client.get("/api/documents").json()["items"][0]["cpf"] == "529.***.***-25"
    detail = client.get(f"/api/documents/{document['id']}").json()
    assert detail["masked"] is True
    assert values_of(detail)["full_name"] == "MARIANA OLIVEIRA DOS SANTOS"
    assert values_of(detail)["rg_number"] == "48.2**.**5-6"


def test_reveal_is_audited(client):
    login(client)
    document = upload(client)
    revealed = client.get(f"/api/documents/{document['id']}", params={"reveal": "true"}).json()
    assert revealed["masked"] is False
    assert values_of(revealed)["cpf"] == "529.982.247-25"
    assert revealed["raw_text"]
    entries = client.get("/api/audit", params={"action": "reveal"}).json()["items"]
    assert [(entry["entity"], entry["entity_id"]) for entry in entries] == [("document", document["id"])]


def test_reader_cannot_reveal(client):
    login(client)
    document = upload(client)
    add_user(client.app, "leitor@exemplo.com", role="reader")
    client.post("/api/auth/logout")
    login(client, "leitor@exemplo.com", PASSWORD)
    assert client.get(f"/api/documents/{document['id']}").status_code == 200
    assert client.get(f"/api/documents/{document['id']}", params={"reveal": "true"}).status_code == 403
    assert client.get(f"/api/people/{document['person_id']}", params={"reveal": "true"}).status_code == 403


def test_saving_masked_values_keeps_the_stored_data(client):
    login(client)
    document = upload(client)
    masked = values_of(client.get(f"/api/documents/{document['id']}").json())
    response = client.put(f"/api/documents/{document['id']}", json={"values": {**masked, "full_name": "NOVO NOME"}})
    assert response.status_code == 200
    revealed = values_of(client.get(f"/api/documents/{document['id']}", params={"reveal": "true"}).json())
    assert revealed["cpf"] == "529.982.247-25"
    assert revealed["rg_number"] == "48.217.395-6"
    assert revealed["full_name"] == "NOVO NOME"
    client.put(f"/api/people/{document['person_id']}", json={"values": {"cpf": "529.***.***-25", "birthplace": "SANTOS-SP"}})
    with client.app_state.session_factory() as session:
        person = session.get(Person, document["person_id"])
        assert person.cpf == "52998224725"
        assert person.birthplace == "SANTOS-SP"
