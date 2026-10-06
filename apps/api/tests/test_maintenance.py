import io
import os
import time
import zipfile

import cv2
import numpy as np
from openpyxl import load_workbook
from reportlab.pdfgen import canvas
from sqlalchemy import select, text

from legivel.db.models import Document, ProcessingJob, Record, ReviewRevision, User
from legivel.imaging.preprocess import deskew
from legivel.services import backups
from legivel.services.jobs import process_next
from tests.conftest import add_user, login
from tests.test_modules import image_bytes

PASSWORD = "senha-do-backup-de-teste-123"


def document(client):
    response = client.post("/api/documents", files={"back": ("rg.jpg", image_bytes(), "image/jpeg")})
    assert response.status_code == 201, response.text
    return response.json()


def pdf_bytes():
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(300, 500))
    for number in range(1, 4):
        pdf.drawString(20, 400, f"Pagina {number}: documento ficticio")
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def test_history_encrypted_author_changes_undo_conflict_and_cascade(client):
    login(client)
    item = document(client)
    target = f"/api/documents/{item['id']}"
    original = next(field["value"] for field in item["fields"] if field["name"] == "full_name")
    reviewed = client.put(target, json={"values": {"full_name": "NOME ALTERADO"}})
    assert reviewed.status_code == 200, reviewed.text
    history = client.get(f"/api/history/document/{item['id']}").json()
    assert history[0]["author"] == "Operador"
    assert history[0]["changes"]["full_name"] == {"before": original, "after": "NOME ALTERADO"}
    with client.app.state.session_factory() as session:
        stored = session.scalar(text('SELECT "before" FROM review_revisions'))
        assert stored.startswith("enc2:") and original not in stored
    undo = f"/api/history/document/{item['id']}/{history[0]['id']}/undo"
    assert client.post(undo).status_code == 200
    assert client.post(undo).status_code == 409
    result = client.get(target + "?reveal=true").json()
    assert next(field["value"] for field in result["fields"] if field["name"] == "full_name") == original
    client.delete(target)
    with client.app.state.session_factory() as session:
        assert not session.scalars(select(ReviewRevision)).all()


def test_pdf_selection_orientation_invalid_ranges_and_queue(client):
    login(client)
    files = {"file": ("paginas.pdf", pdf_bytes(), "application/pdf")}
    assert client.post("/api/pdf/inspect", files=files).json() == {"pages": 3}
    selections = '[{"page": 3, "rotation": 90}, {"page": 1}]'
    response = client.post("/api/pdf/render", files=files, data={"selections": selections})
    assert response.status_code == 200, response.text
    import base64

    from PIL import Image

    pages = response.json()["pages"]
    assert [page["page"] for page in pages] == [3, 1]
    contents = [base64.b64decode(page["image"]) for page in pages]
    first = Image.open(io.BytesIO(contents[0]))
    assert first.width > first.height
    queued = client.post(
        "/api/jobs",
        data={"module": "books"},
        files=[("pages", (f"page-{index}.jpg", content, "image/jpeg")) for index, content in enumerate(contents)],
    )
    assert queued.status_code == 202, queued.text
    assert process_next(client.app)
    assert client.get("/api/jobs").json()[0]["status"] == "completed"
    for selection in ('[{"page":0}]', '[{"page":4}]', '[{"page":1,"rotation":45}]', '[{"page":1},{"page":1}]', "[]"):
        assert client.post("/api/pdf/render", files=files, data={"selections": selection}).status_code == 400
    assert client.post("/api/pdf/inspect", files={"file": ("bad.pdf", b"not a pdf")}).status_code == 400


def test_batch_csv_excel_zip_and_formula_injection(client):
    login(client)
    item = document(client)
    client.put(f"/api/documents/{item['id']}", json={"values": {"full_name": '=HYPERLINK("https://example.invalid")'}})
    payload = {"entity": "document", "ids": [item["id"]], "format": "csv"}
    csv = client.post("/api/export/batch", json=payload)
    assert csv.status_code == 200
    assert "'=HYPERLINK" in csv.content.decode("utf-8-sig")
    xlsx = client.post("/api/export/batch", json={**payload, "format": "xlsx"})
    workbook = load_workbook(io.BytesIO(xlsx.content))
    assert all(cell.data_type != "f" for row in workbook.active for cell in row)
    assert any("'=HYPERLINK" in str(cell.value) for row in workbook.active for cell in row)
    zipped = client.post("/api/export/batch", json={**payload, "format": "zip"})
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
        assert "dados.json" in archive.namelist()
        assert any(name.endswith(".jpg") for name in archive.namelist())
    assert client.post("/api/export/batch", json={**payload, "ids": [999999]}).status_code == 404
    assert client.post("/api/export/batch", json={**payload, "ids": []}).status_code == 422


def test_backup_recovery_integrity_password_and_actual_restore(client):
    login(client)
    item = document(client)
    created = client.post("/api/maintenance/backups", data={"password": PASSWORD})
    assert created.status_code == 200, created.text
    assert b"manifest.json" not in created.content and b"Operador" not in created.content
    files = {"file": ("backup.lgb", created.content, "application/octet-stream")}
    verified = client.post("/api/maintenance/backups/verify", data={"password": PASSWORD}, files=files)
    assert verified.status_code == 200, verified.text
    assert verified.json()["files"] >= 3
    assert client.post("/api/maintenance/backups/verify", data={"password": "senha-errada-123"}, files=files).status_code == 400
    corrupted = bytearray(created.content)
    corrupted[-1] ^= 1
    assert (
        client.post(
            "/api/maintenance/backups/verify", data={"password": PASSWORD}, files={"file": ("bad.lgb", bytes(corrupted))}
        ).status_code
        == 400
    )
    client.put(f"/api/documents/{item['id']}", json={"values": {"full_name": "DEPOIS DO BACKUP"}})
    original = client.get(f"/api/documents/{item['id']}?reveal=true").json()
    response = client.post(
        "/api/maintenance/backups/restore", data={"password": PASSWORD, "confirmation": "RESTAURAR"}, files=files
    )
    assert response.status_code == 200, response.text
    assert not process_next(client.app)
    assert client.put(f"/api/documents/{item['id']}", json={"values": {}}).status_code == 503
    settings = client.app.state.settings
    backups.apply_pending_restore(settings)
    with client.app.state.session_factory() as session:
        restored = session.get(Document, item["id"])
        assert restored.full_name != "DEPOIS DO BACKUP"
        for image in restored.images:
            assert client.app.state.store.load(image.original_path)
    assert not (backups.maintenance_dir(settings) / "restore.pending").exists()
    assert original["id"] == item["id"]


def test_backup_path_traversal_and_incompatible_keys_rejected(client):
    login(client)
    settings = client.app.state.settings
    created = backups.create_backup(settings, PASSWORD)
    manifest, files = backups.read_backup(created, PASSWORD)
    manifest["files"]["../escape.bin"] = "bad"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        import json

        archive.writestr("manifest.json", json.dumps(manifest))
        for name, content in files.items():
            archive.writestr("storage/" + name, content)
    import pytest

    with pytest.raises(ValueError, match="Caminho"):
        backups.read_backup(backups.protect(stream.getvalue(), PASSWORD), PASSWORD)
    other = settings.model_copy(update={"secret_key": "x" * 32})
    with pytest.raises(ValueError, match="chaves"):
        backups.verify_backup(other, created, PASSWORD)


def test_cleanup_keeps_referenced_recent_and_failed_queue_files(client):
    login(client)
    document(client)
    store = client.app.state.store
    orphan = store.save("processed", b"orphan").relative_path
    recent = store.save("processed", b"recent").relative_path
    old = time.time() - 2 * 24 * 3600
    os.utime(client.app.state.settings.storage_dir / orphan, (old, old))
    queued = store.save("queue", image_bytes()).relative_path
    os.utime(client.app.state.settings.storage_dir / queued, (old, old))
    with client.app.state.session_factory() as session:
        session.add(
            ProcessingJob(
                user_id=session.scalar(select(User.id)),
                module="books",
                label="Falha de teste",
                total_pages=1,
                status="failed",
                payload={"paths": [queued]},
            )
        )
        session.commit()
    before = client.get("/api/maintenance").json()
    assert before["unreferenced_files"] == 2 and before["missing_files"] == 0
    cleaned = client.post("/api/maintenance/cleanup").json()
    assert cleaned == {"removed": 1}
    assert (client.app.state.settings.storage_dir / recent).exists()
    assert (client.app.state.settings.storage_dir / queued).exists()
    assert client.get("/api/maintenance").json()["missing_files"] == 0


def test_record_history_restores_title_and_ignores_readonly_fields(client):
    login(client)
    queued = client.post("/api/jobs", data={"module": "books"}, files={"pages": ("pagina.jpg", image_bytes(), "image/jpeg")})
    assert queued.status_code == 202
    process_next(client.app)
    record_id = client.get("/api/jobs").json()[0]["result_id"]
    with client.app.state.session_factory() as session:
        original = session.get(Record, record_id).title
    response = client.put(f"/api/records/{record_id}", json={"values": {"title": "TITULO CORRIGIDO", "words": "999999"}})
    assert response.status_code == 200, response.text
    history = client.get(f"/api/history/record/{record_id}").json()
    assert "words" not in history[0]["changes"]
    assert client.post(f"/api/history/record/{record_id}/{history[0]['id']}/undo").status_code == 200
    with client.app.state.session_factory() as session:
        assert session.get(Record, record_id).title == original


def test_restore_bad_password_does_not_pause_and_keys_recovery_never_overwrites(client, tmp_path):
    login(client)
    settings = client.app.state.settings
    payload = backups.create_backup(settings, PASSWORD)
    response = client.post(
        "/api/maintenance/backups/restore",
        data={"password": "wrong-password-123", "confirmation": "RESTAURAR"},
        files={"file": ("backup.lgb", payload)},
    )
    assert response.status_code == 400
    assert not client.app.state.restore_pending
    source = tmp_path / "backup.lgb"
    source.write_bytes(payload)
    target = tmp_path / "recovered"
    backups.recover_keys(source, target, PASSWORD)
    assert (target / "secret_key.txt").read_text().strip() == settings.secret_key
    import pytest

    with pytest.raises(FileExistsError):
        backups.recover_keys(source, target, PASSWORD)


def test_backup_includes_pending_upload_and_rejects_missing_queue_file(client):
    login(client)
    queued = client.post("/api/jobs", files={"front": ("foto.jpg", image_bytes(), "image/jpeg")}).json()
    settings = client.app.state.settings
    archive = backups.create_backup(settings, PASSWORD)
    manifest, files = backups.verify_backup(settings, archive, PASSWORD)
    assert manifest["tables"]["processing_jobs"][0]["status"] == "queued"
    with client.app.state.session_factory() as session:
        path = session.get(ProcessingJob, queued["id"]).payload["paths"][0]
    assert path in files
    client.app.state.store.delete(path)
    import pytest

    with pytest.raises(ValueError, match="ausentes"):
        backups.create_backup(settings, PASSWORD)


def test_new_features_permissions(client):
    login(client)
    item = document(client)
    add_user(client.app, "reader-new@example.test", role="reader")
    login(client, "reader-new@example.test")
    for path in ("/api/maintenance", f"/api/history/document/{item['id']}"):
        assert client.get(path).status_code == 403
    assert client.post("/api/maintenance/cleanup").status_code == 403
    assert client.post("/api/maintenance/backups", data={"password": PASSWORD}).status_code == 403
    assert client.post("/api/pdf/inspect", files={"file": ("p.pdf", pdf_bytes())}).status_code == 403
    assert client.post("/api/export/batch", json={"entity": "document", "ids": [item["id"]], "format": "csv"}).status_code == 403


def test_deskew_corrects_line_angle_without_changing_blank_images():
    blank = np.full((600, 900, 3), 255, np.uint8)
    assert np.array_equal(blank, deskew(blank))
    source = blank.copy()
    for y in range(100, 500, 40):
        cv2.line(source, (100, y), (800, y + 50), (0, 0, 0), 2)
    corrected = deskew(source)
    assert not np.array_equal(source, corrected)
    mask = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY) < 100
    # Deskew should align long horizontal lines into fewer occupied rows.
    assert np.max(mask.sum(axis=1)) > 500
