import io

import pytest
from PIL import Image

from legivel.imaging.preprocess import InvalidImageError, load_image
from tests.conftest import login
from tests.synthetic import encode_jpeg, photograph, render_rg_back


def huge_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("1", (20_000, 20_000)).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def test_decompression_bomb_is_rejected_before_decoding():
    content = huge_png()
    assert len(content) < 2_000_000
    with pytest.raises(InvalidImageError):
        load_image(content)


def test_upload_of_decompression_bomb_is_refused(client):
    login(client)
    response = client.post("/api/documents", files={"front": ("frente.png", huge_png(), "image/png")})
    assert response.status_code == 400


def test_fake_extension_is_detected_by_content(client):
    login(client)
    script = b"<script>alert(1)</script>"
    response = client.post("/api/documents", files={"front": ("frente.jpg", script, "image/jpeg")})
    assert response.status_code == 400
    pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
    assert client.post("/api/documents", files={"front": ("rg.png", pdf, "image/png")}).status_code == 400


def test_client_file_name_is_never_used_as_path(client, tmp_path):
    login(client)
    image = encode_jpeg(photograph(render_rg_back()))
    response = client.post("/api/documents", files={"back": ("../../../../etc/passwd", image, "image/jpeg")})
    assert response.status_code == 201
    storage = client.app_state.settings.storage_dir
    names = [path.name for path in storage.rglob("*") if path.is_file()]
    assert all(name.endswith(".bin") and len(name) == 36 for name in names)
    assert not any("passwd" in str(path) for path in storage.rglob("*"))


def test_oversized_json_body_is_refused(client):
    body = b'{"email":"' + b"a" * 2_000_000 + b'"}'
    response = client.post("/api/auth/login", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_declared_oversized_upload_is_refused_before_reading(client):
    login(client)
    response = client.post(
        "/api/documents",
        content=b"x",
        headers={"Content-Type": "multipart/form-data; boundary=b", "Content-Length": str(300 * 1024 * 1024)},
    )
    assert response.status_code == 413
