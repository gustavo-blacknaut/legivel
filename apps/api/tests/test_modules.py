import json

from sqlalchemy import text

from legivel.db.models import CardDetail, Record, RecordPage
from legivel.modules.reading_order import analyze_layout
from legivel.ocr.base import TextBox
from tests.conftest import EMAIL, add_user, login, make_client
from tests.synthetic import encode_jpeg, photograph, render_rg_back
from tests.test_validators_modules import build_bank_line


def box(text: str, x0: float, y0: float, x1: float, y1: float, confidence: float = 0.97) -> TextBox:
    return TextBox(text, confidence, x0, y0, x1, y1)


class StaticEngine:
    name = "fake"

    def __init__(self, boxes: list[TextBox]):
        self.boxes = boxes

    def read(self, image):
        return self.boxes


def use_boxes(client, boxes: list[TextBox]) -> None:
    engine = StaticEngine(boxes)
    client.app_state.ocr_engine = engine


def image_bytes() -> bytes:
    return encode_jpeg(photograph(render_rg_back()))


def upload(client, module: str, count: int = 1, options: dict | None = None):
    files = [("pages", (f"p{index}.jpg", image_bytes(), "image/jpeg")) for index in range(count)]
    data = {"module": module, "options": json.dumps(options or {})}
    return client.post("/api/records", data=data, files=files)


CARD_BOXES = [
    box("NUBANK", 40, 30, 200, 70),
    box("4111 1111 1111 1111", 40, 300, 700, 360),
    box("VALID THRU 08/29", 300, 400, 560, 440),
    box("MARIA S OLIVEIRA", 40, 480, 420, 520),
    box("CVV 987", 600, 480, 700, 520),
    box("Platinum", 560, 30, 700, 70),
]


def test_card_module_never_keeps_cvv_full_number_or_image(client):
    login(client)
    use_boxes(client, CARD_BOXES)
    response = upload(client, "cards")
    assert response.status_code == 201
    detail = response.json()
    assert detail["card"]["brand"] == "Visa"
    assert detail["card"]["last4"] == "1111"
    assert detail["card"]["holder_name"] == "MARIA S OLIVEIRA"
    assert detail["card"]["expiry"] == "08/29"
    assert detail["card"]["number_stored"] is False
    assert detail["pages"] == []
    serialized = response.text
    assert "987" not in serialized
    assert "4111111111111111" not in serialized.replace(" ", "")
    with client.app_state.session_factory() as session:
        record = session.get(Record, detail["id"])
        stored = json.dumps(record.data) + (record.search_text or "") + (record.title or "")
        assert "987" not in stored
        assert "41111111" not in stored.replace(" ", "")
        assert session.query(RecordPage).count() == 0
        assert session.get(CardDetail, detail["id"]).full_number is None


def test_card_full_number_is_kept_only_when_enabled_and_encrypted(client):
    login(client)
    response = client.put("/api/settings", json={"values": {"store_card_numbers": True}})
    assert response.json()["values"]["store_card_numbers"] is True
    use_boxes(client, CARD_BOXES)
    detail = upload(client, "cards").json()
    assert detail["card"]["number_stored"] is True
    with client.app_state.session_factory() as session:
        assert session.get(CardDetail, detail["id"]).full_number == "4111111111111111"
        stored = session.execute(text("SELECT full_number FROM card_details")).scalar_one()
        assert stored.startswith("enc2:") and "4111" not in stored


def test_card_number_storage_requires_encryption(tmp_path, database_url):
    with make_client(tmp_path, database_url, encryption_enabled=False, encryption_key="") as unencrypted:
        add_user(unencrypted.app, EMAIL)
        login(unencrypted)
        response = unencrypted.put("/api/settings", json={"values": {"store_card_numbers": True}})
        assert response.status_code == 400


def test_reader_cannot_upload_or_delete_records(client):
    add_user(client.app, "leitor@exemplo.com.br", role="reader")
    login(client)
    use_boxes(client, [box("Relatório anual", 40, 40, 900, 90)])
    record_id = upload(client, "books").json()["id"]
    client.post("/api/auth/logout")
    login(client, "leitor@exemplo.com.br")
    assert client.get(f"/api/records/{record_id}").status_code == 200
    assert upload(client, "books").status_code == 403
    assert client.delete(f"/api/records/{record_id}").status_code == 403


def test_records_require_login(client):
    assert client.get("/api/records").status_code == 401
    assert client.get("/api/modules").status_code == 401


def test_finance_module_reads_bank_slip(client):
    login(client)
    line = build_bank_line("001", 9999, 25990, "0" * 6 + "1234567890123456789")
    use_boxes(
        client,
        [
            box("LOCAL DE PAGAMENTO PAGAVEL EM QUALQUER BANCO", 40, 20, 900, 50),
            box("BENEFICIARIO", 40, 70, 200, 90),
            box("ESCOLA MODELO LTDA", 40, 95, 400, 120),
            box("CNPJ 11.222.333/0001-81", 500, 95, 900, 120),
            box(line[:24], 40, 400, 500, 430),
            box(line[24:], 520, 400, 990, 430),
        ],
    )
    detail = upload(client, "finance").json()
    assert detail["kind"] == "boleto"
    values = {field["name"]: field["value"] for field in detail["fields"]}
    assert values["amount"] == "R$ 259,90"
    assert values["beneficiary"] == "ESCOLA MODELO LTDA"
    assert values["beneficiary_cnpj"] == "11.222.333/0001-81"
    assert values["digitable_line"].replace(" ", "").replace(".", "") == line
    assert detail["issues"] == []


def test_books_module_keeps_column_order_and_exports(client):
    login(client)
    use_boxes(
        client,
        [
            box("CAPITULO UM", 100, 40, 900, 110),
            box("Primeira linha da esquerda", 60, 160, 470, 190),
            box("segunda linha da esquerda", 60, 200, 470, 230),
            box("terceira linha da esquerda", 60, 240, 470, 270),
            box("Primeira linha da direita", 530, 160, 940, 190),
            box("segunda linha da direita", 530, 200, 940, 230),
            box("terceira linha da direita", 530, 240, 940, 270),
        ],
    )
    detail = upload(client, "books", count=2).json()
    assert detail["page_count"] == 2
    text = detail["pages"][0]["text"]
    assert text.index("terceira linha da esquerda") < text.index("Primeira linha da direita")
    assert detail["pages"][0]["columns"] == 2
    record_id = detail["id"]
    pdf = client.get(f"/api/records/{record_id}/export/pdf")
    assert pdf.content[:4] == b"%PDF"
    assert pdf.headers["content-type"] == "application/pdf"
    markdown = client.get(f"/api/records/{record_id}/export/md").text
    assert "## CAPITULO UM" in markdown
    assert "Primeira linha da esquerda" in client.get(f"/api/records/{record_id}/export/txt").text
    assert client.get(f"/api/records/{record_id}/export/docx").status_code == 404


def test_scanner_module_keeps_original_and_enhanced_pages(client):
    login(client)
    use_boxes(client, [box("Contrato de locação", 40, 40, 600, 90)])
    detail = upload(client, "scanner", count=3, options={"mode": "bw"}).json()
    assert detail["page_count"] == 3
    assert detail["kind"] == "bw"
    with client.app_state.session_factory() as session:
        pages = session.query(RecordPage).filter_by(record_id=detail["id"]).all()
        assert all(page.original_path and page.processed_path for page in pages)
    assert client.get(detail["pages"][0]["full_url"]).headers["content-type"] == "image/jpeg"


def test_records_listing_review_delete_and_global_search(client):
    login(client)
    use_boxes(client, [box("Relatório anual da cooperativa", 40, 40, 900, 90)])
    detail = upload(client, "books").json()
    listing = client.get("/api/records", params={"module": "books"}).json()
    assert listing["total"] == 1
    reviewed = client.put(f"/api/records/{detail['id']}", json={"values": {"title": "Relatório 2026", "pages": "99"}}).json()
    assert reviewed["title"] == "Relatório 2026"
    assert reviewed["status"] == "reviewed"
    assert next(field for field in reviewed["fields"] if field["name"] == "pages")["value"] == "1"
    hits = client.get("/api/search", params={"q": "cooperativa"}).json()
    assert hits["total"] == 1
    assert hits["items"][0]["url"] == f"/registros/{detail['id']}"
    assert client.delete(f"/api/records/{detail['id']}").status_code == 204
    assert client.get("/api/search", params={"q": "cooperativa"}).json()["total"] == 0


def test_rejects_too_many_pages_and_unknown_module(client):
    login(client)
    assert upload(client, "cards", count=2).status_code == 400
    assert upload(client, "naoexiste").status_code == 400


def test_reading_order_single_column():
    boxes = [box("linha um", 50, 50, 500, 80), box("linha dois", 50, 90, 480, 120), box("linha tres", 50, 130, 490, 160)]
    layout = analyze_layout(boxes)
    assert layout.columns == 1
    assert layout.text == "linha um linha dois linha tres"


def test_languages_follow_the_reading_settings(client):
    login(client)
    assert [item["code"] for item in client.get("/api/languages").json()] == ["pt", "en", "es"]
    client.put("/api/settings", json={"values": {"reading_languages": "pt,ja"}})
    assert [item["code"] for item in client.get("/api/languages").json()] == ["pt", "ja"]
    assert client.put("/api/settings", json={"values": {"reading_languages": "pt,xx"}}).status_code == 400
