import importlib.util
import io
from pathlib import Path

from PIL import Image
from sqlalchemy import func, select, text

from legivel.db.models import Document, ProcessingJob
from legivel.security.crypto import FIELD_PREFIX
from legivel.services.jobs import process_next, recover_jobs
from tests.conftest import add_user, login
from tests.test_modules import image_bytes


def enqueue_document(client, **data):
    return client.post("/api/jobs", data=data, files={"front": ("foto.jpg", image_bytes(), "image/jpeg")})


def test_queue_encrypted_restart_and_exactly_one_result(client):
    login(client)
    queued = enqueue_document(client)
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["id"]
    with client.app.state.session_factory() as session:
        job = session.get(ProcessingJob, job_id)
        paths = job.payload["paths"]
        assert paths and client.app.state.store.encrypted
        assert session.scalar(text("SELECT payload FROM processing_jobs WHERE id = :id"), {"id": job_id}).startswith(FIELD_PREFIX)
        job.status = "running"
        session.commit()
    recover_jobs(client.app)
    assert process_next(client.app)
    assert not process_next(client.app)
    jobs = client.get("/api/jobs").json()
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["completed_pages"] == 1
    detail = client.get(f"/api/documents/{jobs[0]['result_id']}").json()
    assert detail["field_regions"]
    assert all(0 <= v <= 1 for region in detail["field_regions"].values() for v in region["rect"])
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count(Document.id))) == 1
        assert session.get(ProcessingJob, job_id).payload == {}
    for path in paths:
        assert not (client.app.state.settings.storage_dir / path).exists()


def test_failed_queue_can_retry_only_failed_and_cancel_discards_upload(client):
    login(client)
    job = enqueue_document(client).json()
    engine = client.app.state.ocr_engine

    class BrokenEngine:
        name = "broken"

        def read(self, image):
            raise RuntimeError("private input should never appear in response")

    client.app.state.ocr_engine = BrokenEngine()
    assert process_next(client.app)
    assert client.get("/api/jobs").json()[0]["status"] == "failed"
    assert "private input" not in client.get("/api/jobs").text
    client.app.state.ocr_engine = engine
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 200
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409
    with client.app.state.session_factory() as session:
        paths = session.get(ProcessingJob, job["id"]).payload["paths"]
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    assert not process_next(client.app)
    for path in paths:
        assert not (client.app.state.settings.storage_dir / path).exists()


def test_queue_cancel_during_ocr_rolls_back_result(client):
    login(client)
    job = enqueue_document(client).json()
    original = client.app.state.ocr_engine

    class CancellingEngine:
        name = "cancel"

        def read(self, image):
            client.post(f"/api/jobs/{job['id']}/cancel")
            return original.read(image)

    client.app.state.ocr_engine = CancellingEngine()
    process_next(client.app)
    assert client.get("/api/jobs").json()[0]["status"] == "cancelled"
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count(Document.id))) == 0


def test_duplicates_keep_link_and_replace(client):
    login(client)
    enqueue_document(client)
    process_next(client.app)
    existing = client.get("/api/jobs").json()[0]["result_id"]
    duplicate = enqueue_document(client)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["document_id"] == existing
    linked = enqueue_document(client, duplicate="link").json()
    assert linked["status"] == "completed" and linked["result_id"] == existing
    replacement = enqueue_document(client, duplicate="replace")
    assert replacement.status_code == 202
    assert client.get(f"/api/documents/{existing}").status_code == 200
    process_next(client.app)
    assert client.get(f"/api/documents/{existing}").status_code == 404
    assert client.get("/api/jobs").json()[0]["status"] == "completed"
    kept = enqueue_document(client, duplicate="keep")
    assert kept.status_code == 202
    process_next(client.app)
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count(Document.id))) == 2


def test_queue_supports_multi_page_reading_and_rejects_cards(client):
    login(client)
    files = [("pages", (f"p{i}.jpg", image_bytes(), "image/jpeg")) for i in range(2)]
    response = client.post("/api/jobs", data={"module": "books"}, files=files)
    assert response.status_code == 202
    process_next(client.app)
    job = client.get("/api/jobs").json()[0]
    assert job["status"] == "completed" and job["completed_pages"] == 2
    assert client.get(f"/api/records/{job['result_id']}").json()["page_count"] == 2
    assert client.post("/api/jobs", data={"module": "cards"}, files=files).status_code == 400


def test_jobs_and_organization_are_private_and_permissions_checked(client):
    login(client)
    job = enqueue_document(client).json()
    process_next(client.app)
    document_id = client.get("/api/jobs").json()[0]["result_id"]
    path = f"/api/organization/document/{document_id}"
    assert client.put(path, json={"folder": "Clientes", "tags": [" mensal ", "mensal"]}).json()["tags"] == ["mensal"]
    search = client.post("/api/saved-searches", json={"name": "Pendentes", "path": "/documentos?status=pending_review"}).json()
    assert client.post("/api/saved-searches", json={"name": "X", "path": "//example.com"}).status_code == 422
    add_user(client.app, "leitor@exemplo.com.br", role="reader")
    client.post("/api/auth/logout")
    login(client, "leitor@exemplo.com.br")
    assert client.get("/api/jobs").json() == []
    assert client.post(f"/api/jobs/{job['id']}/cancel").status_code == 404
    assert enqueue_document(client).status_code == 403
    assert client.get(path).json() == {"folder": "", "tags": []}
    assert client.delete(f"/api/saved-searches/{search['id']}").status_code == 404


def test_capture_quality_advisory_and_rejects_invalid_files(client):
    login(client)
    buffer = io.BytesIO()
    Image.new("RGB", (700, 900), (25, 25, 25)).save(buffer, "PNG")
    response = client.post("/api/capture/check", files={"photo": ("dark.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 200
    assert response.json()["brightness"] < 65
    assert len(response.json()["warnings"]) >= 2
    assert client.post("/api/capture/check", files={"photo": ("x.png", b"garbage", "image/png")}).status_code == 400


def test_redaction_removes_pixels_and_has_no_text_layer_or_original(client):
    login(client)
    enqueue_document(client)
    process_next(client.app)
    document_id = client.get("/api/jobs").json()[0]["result_id"]
    detail = client.get(f"/api/documents/{document_id}").json()
    page_id = detail["pages"][0]["id"]
    body = {"regions": [{"page_id": page_id, "rect": [0, 0, 1, 1]}], "preview_page": page_id}
    path = f"/api/redaction/document/{document_id}"
    preview = client.post(path, json=body)
    assert preview.status_code == 200
    image = Image.open(io.BytesIO(preview.content))
    assert image.getextrema() == ((0, 0), (0, 0), (0, 0))
    body["preview_page"] = None
    result = client.post(path, json=body)
    assert result.status_code == 200 and result.content.startswith(b"%PDF")
    from pypdf import PdfReader
    pdf = PdfReader(io.BytesIO(result.content))
    assert all(not page.extract_text().strip() for page in pdf.pages)
    assert not pdf.attachments
    body["regions"][0]["page_id"] = page_id + 999
    assert client.post(path, json=body).status_code == 400
    body["regions"][0]["rect"] = [1, 0, 0, 1]
    assert client.post(path, json=body).status_code == 422


def test_installer_preserves_existing_configuration_and_keys(tmp_path):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("installer", root / "scripts" / "instalar.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / ".env.example").write_text("LEGIVEL_PORT=8091\nLEGIVEL_SECRET_KEY=\n", encoding="utf-8")
    module.prepare_files(tmp_path, 8099)
    assert "8099" in (tmp_path / ".env").read_text()
    original = {name: (tmp_path / "secrets" / name).read_bytes() for name in module.SECRET_NAMES}
    module.prepare_files(tmp_path, 8888)
    assert original == {name: (tmp_path / "secrets" / name).read_bytes() for name in module.SECRET_NAMES}
    assert "8099" in (tmp_path / ".env").read_text()
