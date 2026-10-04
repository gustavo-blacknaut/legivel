from app.db.models import Document, Person
from tests.conftest import login
from tests.synthetic import encode_jpeg, photograph, render_rg_back


def upload_rg(client, doc_type=None):
    image = encode_jpeg(photograph(render_rg_back()))
    return client.post(
        "/api/documents",
        data={"doc_type": doc_type} if doc_type else {},
        files={"front": ("frente.jpg", image, "image/jpeg"), "back": ("verso.jpg", image, "image/jpeg")},
    )


def field_values(detail):
    return {field["name"]: field["value"] for field in detail["fields"]}


def test_overview_starts_empty(client):
    login(client)
    overview = client.get("/api/overview").json()
    assert overview["stats"] == {"documents": 0, "pending": 0, "people": 0}
    assert overview["documents"] == []


def test_upload_identifies_document_type_automatically(client):
    login(client)
    response = upload_rg(client)
    assert response.status_code == 201
    detail = response.json()
    assert detail["doc_type"] == "rg"
    assert detail["type_detected"] is True
    assert field_values(detail)["full_name"] == "MARIANA OLIVEIRA DOS SANTOS"
    assert {page["side"] for page in detail["pages"]} == {"front", "back"}


def test_full_flow_upload_review_and_delete(client):
    login(client)
    detail = upload_rg(client).json()
    document_id = detail["id"]
    values = field_values(detail)
    assert values["cpf"] == "529.982.247-25"

    page = detail["pages"][0]
    assert client.get(page["thumbnail_url"]).headers["content-type"] == "image/webp"
    assert client.get(page["original_url"]).content[:2] == b"\xff\xd8"

    saved = client.put(
        f"/api/documents/{document_id}",
        json={"values": {**values, "full_name": "MARIANA O. DOS SANTOS", "unknown_field": "x"}},
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "reviewed"
    assert saved.json()["reviewed_manually"] is True

    with client.app_state.session_factory() as session:
        person = session.query(Person).one()
        assert person.cpf == "52998224725"
        assert person.full_name == "MARIANA O. DOS SANTOS"

    second = upload_rg(client).json()
    client.put(f"/api/documents/{second['id']}", json={"values": field_values(second)})
    people = client.get("/api/people").json()["items"]
    assert len(people) == 1
    assert people[0]["documents"] == 2

    storage_dir = client.app_state.settings.storage_dir
    assert any(storage_dir.rglob("*.bin"))
    assert client.delete(f"/api/people/{people[0]['id']}").status_code == 204
    with client.app_state.session_factory() as session:
        assert session.query(Person).count() == 0
        assert session.query(Document).count() == 0
    assert not any(storage_dir.rglob("*.bin"))


def test_delete_single_document(client):
    login(client)
    document_id = upload_rg(client).json()["id"]
    assert client.delete(f"/api/documents/{document_id}").status_code == 204
    assert client.get(f"/api/documents/{document_id}").status_code == 404


def test_rejects_invalid_image(client):
    login(client)
    response = client.post("/api/documents", files={"front": ("x.jpg", b"garbage", "image/jpeg")})
    assert response.status_code == 400
    assert "imagem válida" in response.json()["detail"]


def test_upload_without_images_is_rejected(client):
    login(client)
    response = client.post("/api/documents", data={"doc_type": "rg"})
    assert response.status_code == 400
    assert "pelo menos uma foto" in response.json()["detail"]


def test_reprocess_reruns_ocr_and_can_force_type(client):
    login(client)
    detail = upload_rg(client).json()
    client.put(f"/api/documents/{detail['id']}", json={"values": {"full_name": "NOME CORRIGIDO"}})

    reprocessed = client.post(f"/api/documents/{detail['id']}/reprocess", json={}).json()
    assert reprocessed["status"] == "pending_review"
    assert field_values(reprocessed)["full_name"] == "MARIANA OLIVEIRA DOS SANTOS"
    assert len(reprocessed["pages"]) == 2

    forced = client.post(f"/api/documents/{detail['id']}/reprocess", json={"doc_type": "cpf"}).json()
    assert forced["doc_type"] == "cpf"
    assert forced["type_detected"] is False
    assert client.post(f"/api/documents/{detail['id']}/reprocess", json={"doc_type": "xyz"}).status_code == 400


def test_overview_lists_new_documents(client):
    login(client)
    upload_rg(client)
    overview = client.get("/api/overview").json()
    assert overview["stats"]["documents"] == 1
    assert overview["stats"]["pending"] == 1
    assert overview["documents"][0]["full_name"] == "MARIANA OLIVEIRA DOS SANTOS"
    assert overview["documents"][0]["thumbnail_url"].startswith("/api/images/")
