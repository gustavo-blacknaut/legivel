import io
from datetime import timedelta

from PIL import Image

from legivel.db.base import utc_now
from legivel.db.models import Document, DocumentImage
from legivel.security.crypto import is_encrypted
from legivel.services.retention import run_retention
from tests.conftest import add_user, login, make_client
from tests.synthetic import encode_jpeg, photograph, render_rg_back


def png_bytes(size=(64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (30, 120, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def rg_photo() -> bytes:
    return encode_jpeg(photograph(render_rg_back()))


def upload(client, content: bytes, name: str = "verso.jpg", mime: str = "image/jpeg"):
    return client.post("/api/documents", files={"back": (name, content, mime)})


def test_runtime_settings_override_environment_defaults(client):
    login(client)
    initial = client.get("/api/settings").json()
    assert initial["values"]["upload_max_mb"] == 15
    assert initial["overridden"] == []
    saved = client.put("/api/settings", json={"values": {"upload_max_mb": 5, "instance_name": "Cartório Central"}}).json()
    assert saved["values"]["upload_max_mb"] == 5
    assert set(saved["overridden"]) == {"upload_max_mb", "instance_name"}
    assert client.get("/api/public/instance").json()["name"] == "Cartório Central"
    restored = client.put("/api/settings", json={"values": {"upload_max_mb": None}}).json()
    assert restored["values"]["upload_max_mb"] == 15


def test_invalid_runtime_values_are_rejected(client):
    login(client)
    for values in ({"upload_max_mb": 0}, {"ocr_device": "tpu"}, {"database_url": "x"}, {"upload_formats": "gif"}):
        assert client.put("/api/settings", json={"values": values}).status_code == 400


def test_upload_format_allow_list(client):
    login(client)
    client.put("/api/settings", json={"values": {"upload_formats": "jpeg"}})
    response = upload(client, png_bytes(), "frente.png", "image/png")
    assert response.status_code == 415
    assert "JPEG" in response.json()["detail"]
    assert upload(client, rg_photo()).status_code == 201


def test_upload_size_limit_follows_setting(client):
    login(client)
    client.put("/api/settings", json={"values": {"upload_max_mb": 1}})
    response = upload(client, rg_photo() + b"0" * (1024 * 1024))
    assert response.status_code == 413


def test_originals_can_be_compressed(client):
    login(client)
    client.put("/api/settings", json={"values": {"compress_originals": True, "image_quality": 60}})
    big = io.BytesIO()
    Image.new("RGB", (4200, 2800), (200, 210, 200)).save(big, format="PNG")
    document = upload(client, big.getvalue(), "grande.png", "image/png").json()
    with client.app_state.session_factory() as session:
        image = session.get(DocumentImage, document["pages"][0]["id"])
        content = client.app_state.store.load(image.original_path)
    assert image.original_mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(content)).size) == 3000


def test_storage_without_encryption(tmp_path, database_url):
    with make_client(tmp_path, database_url, encryption_enabled=False, encryption_key="") as client:
        add_user(client.app, "admin@exemplo.com")
        login(client, "admin@exemplo.com")
        document = upload(client, rg_photo()).json()
        assert client.get("/api/system").json()["encrypted_storage"] is False
        with client.app_state.session_factory() as session:
            image = session.get(DocumentImage, document["pages"][0]["id"])
        raw = (tmp_path / "storage" / image.original_path).read_bytes()
        assert not is_encrypted(raw)
        assert client.get(document["pages"][0]["original_url"]).status_code == 200


def test_retention_deletes_old_documents(client):
    login(client)
    old = upload(client, rg_photo()).json()
    recent = upload(client, rg_photo()).json()
    with client.app_state.session_factory() as session:
        session.get(Document, old["id"]).processed_at = utc_now() - timedelta(days=40)
        session.commit()
    settings = client.app_state.settings
    assert run_retention(client.app_state.session_factory, client.app_state.store, settings) == 0
    client.put("/api/settings", json={"values": {"retention_days": 30}})
    assert run_retention(client.app_state.session_factory, client.app_state.store, settings) == 1
    assert client.get(f"/api/documents/{old['id']}").status_code == 404
    assert client.get(f"/api/documents/{recent['id']}").status_code == 200
    actions = {item["action"] for item in client.get("/api/audit").json()["items"]}
    assert "retention" in actions


def test_logo_upload_and_public_url(client):
    login(client)
    assert client.get("/api/public/instance").json()["logo_url"] is None
    response = client.put("/api/settings/logo", files={"logo": ("logo.png", png_bytes(), "image/png")})
    assert response.status_code == 204
    url = client.get("/api/public/instance").json()["logo_url"]
    client.post("/api/auth/logout")
    logo = client.get(url)
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"


def test_system_reports_ocr_device_and_timing(client):
    login(client)
    upload(client, rg_photo())
    system = client.get("/api/system").json()
    assert system["database"] in ("sqlite", "postgresql")
    assert system["ocr_status"]["engine"] == "fake"
    assert system["ocr_status"]["images"] >= 1
    assert system["ocr_status"]["image_average_ms"] is not None
