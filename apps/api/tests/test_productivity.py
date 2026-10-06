from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text

from legivel.db.models import AppSetting, Document, Record
from legivel.services import backups
from tests.conftest import add_user, login
from tests.test_modules import image_bytes


def template_body():
    return {
        "name": "Contrato",
        "fields": [
            {"name": "custom_customer", "label": "Cliente", "kind": "text", "required": True},
            {"name": "custom_expiry", "label": "Validade do contrato", "kind": "date", "expiration": True},
        ],
    }


def reading(client, module="scanner"):
    response = client.post("/api/records", data={"module": module}, files=[("pages", ("scan.jpg", image_bytes(), "image/jpeg"))])
    assert response.status_code == 201, response.text
    return response.json()


def test_template_snapshot_encrypted_fields_history_exports_and_backup(client):
    login(client)
    template = client.post("/api/document-templates", json=template_body()).json()
    item = reading(client)
    target = f"/api/records/{item['id']}"
    assert client.post(target + "/template", json={"template_id": template["id"]}).status_code == 200
    detail = client.get(target).json()
    assert detail["template"]["name"] == "Contrato"
    assert any(field["name"] == "custom_customer" and field["issues"] for field in detail["fields"])
    assert detail["pages"][0]["original_url"]
    values = {"custom_customer": "CLIENTE PRIVADO", "custom_expiry": "2026-10-20"}
    assert client.put(target, json={"values": values}).status_code == 200
    with client.app.state.session_factory() as session:
        raw = session.scalar(text("SELECT data FROM records WHERE id = :id"), {"id": item["id"]})
        assert raw.startswith("enc2:") and "CLIENTE PRIVADO" not in raw
    history = client.get(f"/api/history/record/{item['id']}").json()
    assert history[0]["changes"]["custom_customer"]["after"] == "CLIENTE PRIVADO"
    assert client.post(f"/api/history/record/{item['id']}/{history[0]['id']}/undo").status_code == 200
    assert next(field["value"] for field in client.get(target).json()["fields"] if field["name"] == "custom_customer") == ""
    client.put(target, json={"values": values})
    csv = client.post("/api/export/batch", json={"entity": "record", "ids": [item["id"]], "format": "csv"})
    assert "CLIENTE PRIVADO" in csv.content.decode("utf-8-sig")
    changed = {"name": "Modelo atualizado", "fields": [{"name": "custom_new", "label": "Outro"}]}
    assert client.put(f"/api/document-templates/{template['id']}", json=changed).status_code == 200
    assert client.delete(f"/api/document-templates/{template['id']}").status_code == 204
    detail = client.get(target).json()
    assert detail["template"]["name"] == "Contrato"
    assert next(field["value"] for field in detail["fields"] if field["name"] == "custom_customer") == "CLIENTE PRIVADO"
    assert client.post(target + "/template", json={"template_id": template["id"]}).status_code == 409
    password = "backup-com-modelo-12345"
    download = client.post("/api/maintenance/backups", data={"password": password})
    assert download.status_code == 200
    backups.verify_backup(client.app.state.settings, download.content, password)


def test_template_validation_and_permission_boundaries(client):
    login(client)
    for body in (
        {**template_body(), "name": "   "},
        {**template_body(), "fields": [{"name": "full_number", "label": "Número"}]},
        {**template_body(), "fields": [{"name": "custom_x", "label": "   "}]},
        {**template_body(), "fields": [{"name": "custom_x", "label": "X", "expiration": True}]},
        {**template_body(), "fields": [template_body()["fields"][0]] * 2},
        {
            **template_body(),
            "fields": [
                {"name": "custom_a", "label": "A", "kind": "date", "expiration": True},
                {"name": "custom_b", "label": "B", "kind": "date", "expiration": True},
            ],
        },
    ):
        assert client.post("/api/document-templates", json=body).status_code == 422
    template = client.post("/api/document-templates", json=template_body()).json()
    item = reading(client)
    add_user(client.app, "reader@exemplo.com", role="reader")
    login(client, "reader@exemplo.com")
    assert client.get("/api/document-templates").status_code == 200
    assert client.post("/api/document-templates", json=template_body()).status_code == 403
    assert client.put(f"/api/document-templates/{template['id']}", json=template_body()).status_code == 403
    assert client.delete(f"/api/document-templates/{template['id']}").status_code == 403
    assert client.post(f"/api/records/{item['id']}/template", json={"template_id": template["id"]}).status_code == 403
    assert client.get("/api/review/queue").status_code == 403
    assert client.get("/api/expirations").status_code == 200


def test_review_queue_pending_only_stable_order_and_limit(client):
    login(client)
    with client.app.state.session_factory() as session:
        earlier = datetime(2026, 10, 1, tzinfo=UTC)
        document = Document(doc_type="rg", full_name="Primeiro", status="pending_review", processed_at=earlier)
        record = Record(
            module="books", title="Segundo", status="pending_review", created_at=earlier + timedelta(hours=1), data={}
        )
        reviewed = Record(module="books", title="Já revisado", status="reviewed", data={})
        session.add_all([document, record, reviewed])
        session.commit()
        ids = document.id, record.id
    result = client.get("/api/review/queue").json()
    assert result["total"] == 2
    assert [(item["entity"], item["id"]) for item in result["items"]] == [("document", ids[0]), ("record", ids[1])]
    assert len(client.get("/api/review/queue?limit=1").json()["items"]) == 1
    assert client.get("/api/review/queue?entity=record").json()["total"] == 1
    assert client.get("/api/review/queue?limit=201").status_code == 422


def test_expiration_windows_timezone_template_dates_and_user_preferences(client, monkeypatch):
    login(client)
    # At 01:00 UTC it is still October 5 in São Paulo.
    monkeypatch.setattr("legivel.web.product_routes.utc_now", lambda: datetime(2026, 10, 6, 1, tzinfo=UTC))
    with client.app.state.session_factory() as session:
        session.add(AppSetting(key="timezone", value="America/Sao_Paulo"))
        for expiry in (date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 20), date(2027, 1, 1), None):
            session.add(Document(doc_type="cnh", full_name="DATA DE TESTE", valid_until=expiry))
        template = {"name": "Contrato", "fields": [{"name": "custom_expiry", "kind": "date", "expiration": True}]}
        session.add_all(
            [
                Record(
                    module="scanner",
                    title="Contrato vence",
                    data={"template": template, "fields": {"custom_expiry": "2026-10-07"}},
                ),
                Record(
                    module="scanner", title="Data inválida", data={"template": template, "fields": {"custom_expiry": "inválida"}}
                ),
            ]
        )
        session.commit()
    result = client.get("/api/expirations").json()
    assert result["today"] == "2026-10-05"
    assert result["overdue"] == 1 and result["due"] == 3 and result["total"] == 4
    assert [item["days_left"] for item in result["items"]] == [-1, 0, 2, 15]
    due = client.get("/api/expirations?status=due&page_size=1&page=2").json()
    assert due["filtered_total"] == 3 and due["items"][0]["days_left"] == 2
    assert client.get("/api/expirations?status=overdue").json()["filtered_total"] == 1
    assert client.get("/api/expirations?page_size=101").status_code == 422
    assert client.put("/api/expirations/preferences", json={"days": 7}).status_code == 200
    assert client.get("/api/expirations").json()["total"] == 3
    assert client.put("/api/expirations/preferences", json={"days": 999}).status_code == 422
    add_user(client.app, "other@exemplo.com", role="reader")
    login(client, "other@exemplo.com")
    assert client.get("/api/expirations").json()["days"] == 30


def test_model_only_on_supported_modules_and_missing_records(client):
    login(client)
    template = client.post("/api/document-templates", json=template_body()).json()
    with client.app.state.session_factory() as session:
        item = Record(module="cards", data={})
        session.add(item)
        session.commit()
        item_id = item.id
    assert client.post(f"/api/records/{item_id}/template", json={"template_id": template["id"]}).status_code == 400
    assert client.post("/api/records/999999/template", json={"template_id": template["id"]}).status_code == 404
    item = reading(client)
    assert client.post(f"/api/records/{item['id']}/template", json={"template_id": "nonexistent"}).status_code == 404
    with client.app.state.session_factory() as session:
        assert session.scalar(select(Record).where(Record.id == item["id"])).data.get("template") is None


def test_expiration_bills_and_cards_use_date_and_last_day_of_month(client, monkeypatch):
    login(client)
    monkeypatch.setattr("legivel.web.product_routes.utc_now", lambda: datetime(2026, 10, 6, 12, tzinfo=UTC))
    with client.app.state.session_factory() as session:
        session.add_all(
            [
                Record(module="finance", title="Boleto", data={"fields": {"due_date": "07/10/2026"}}),
                Record(module="cards", title="Cartão", data={"fields": {"expiry": "10/26"}}),
                Record(module="cards", title="Data inválida", data={"fields": {"expiry": "13/26"}}),
            ]
        )
        session.commit()
    items = client.get("/api/expirations").json()["items"]
    assert [item["date"] for item in items] == ["2026-10-07", "2026-10-31"]
