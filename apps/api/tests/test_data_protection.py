import base64
import os

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text

from legivel.db.models import CardDetail, Document, DocumentImage, Person, RecordPage
from legivel.ocr.base import TextBox
from legivel.security.crypto import KeyRing, generate_key
from legivel.security.fields import blind_index, configure_fields
from legivel.security.rotation import pending, reencrypt
from legivel.storage.file_store import FileStore
from tests.conftest import add_user, login, make_client
from tests.synthetic import encode_jpeg, photograph, render_rg_back
from tests.test_modules import CARD_BOXES
from tests.test_modules import StaticEngine as StaticBoxes

CPF = "52998224725"


def upload(client):
    image = encode_jpeg(photograph(render_rg_back()))
    return client.post("/api/documents", files={"back": ("verso.jpg", image, "image/jpeg")}).json()


def raw_rows(client, sql: str):
    with client.app_state.session_factory() as session:
        return session.execute(text(sql)).all()


def test_sensitive_columns_are_encrypted_at_rest(client):
    login(client)
    upload(client)
    people = raw_rows(client, "SELECT cpf, cpf_index FROM people")
    documents = raw_rows(client, "SELECT cpf, rg_number, raw_text, extra_fields FROM documents")
    assert people and documents
    for value in [*people[0][:1], *documents[0]]:
        assert value.startswith("enc2:")
        assert CPF[:6] not in value
    assert len(people[0][1]) == 64


def test_cpf_search_uses_blind_index(client):
    login(client)
    upload(client)
    assert client.get("/api/people", params={"q": "538.965.013-13"}).json()["total"] in (0, 1)
    person = client.get("/api/people").json()["items"][0]
    with client.app_state.session_factory() as session:
        full = session.get(Person, person["id"]).cpf
    found = client.get("/api/people", params={"q": full}).json()
    assert found["total"] == 1
    assert client.get("/api/people", params={"q": full[:6]}).json()["total"] == 0


def test_same_cpf_is_merged_into_one_person(client):
    login(client)
    first = upload(client)
    second = upload(client)
    assert first["person_id"] == second["person_id"]


def test_blind_index_depends_on_the_key():
    configure_fields(KeyRing(generate_key()), "x" * 32)
    first = blind_index(CPF)
    configure_fields(KeyRing(generate_key()), "x" * 32)
    assert blind_index(CPF) != first
    assert blind_index(None) is None


def test_old_keys_still_decrypt_and_new_writes_use_current_key():
    old, new = generate_key(), generate_key()
    payload = KeyRing(old).encrypt(b"documento", b"originals/aa/x.bin")
    ring = KeyRing(new, [old])
    assert ring.decrypt(payload, b"originals/aa/x.bin") == b"documento"
    assert ring.needs_rotation(payload)
    assert not ring.needs_rotation(ring.encrypt(b"documento"))


def test_legacy_file_format_is_still_readable():
    key = generate_key()
    ring = KeyRing(key)
    nonce = os.urandom(12)


    legacy = b"GOCR1" + nonce + AESGCM(base64.urlsafe_b64decode(key)).encrypt(nonce, b"antigo", b"p")
    assert ring.decrypt(legacy, b"p") == b"antigo"
    assert ring.needs_rotation(legacy)


def test_key_rotation_reencrypts_rows_and_files(tmp_path, database_url):
    old_key = generate_key()
    with make_client(tmp_path, database_url, encryption_key=old_key) as client:
        add_user(client.app, "admin@exemplo.com")
        login(client, "admin@exemplo.com")
        document = upload(client)
        before = raw_rows(client, "SELECT rg_number FROM documents")[0][0]
    new_key = generate_key()
    with make_client(tmp_path, database_url, encryption_key=new_key, encryption_old_keys=old_key) as client:
        login(client, "admin@exemplo.com")
        ring = client.app_state.settings.key_ring()
        factory = client.app_state.session_factory
        with factory() as session:
            assert pending(session, ring)
        report = reencrypt(factory, client.app_state.store, ring)
        assert report.documents == 1 and report.files > 0
        with factory() as session:
            assert not pending(session, ring)
            image = session.get(DocumentImage, document["pages"][0]["id"])
            payload = (tmp_path / "storage" / image.original_path).read_bytes()
            assert not ring.needs_rotation(payload)
        after = raw_rows(client, "SELECT rg_number FROM documents")[0][0]
        assert after != before
    with make_client(tmp_path, database_url, encryption_key=new_key) as client:
        login(client, "admin@exemplo.com")
        detail = client.get(f"/api/documents/{document['id']}").json()
        assert detail["full_name"]
        assert client.get(document["pages"][0]["original_url"]).status_code == 200


def test_plaintext_rows_from_older_versions_are_protected(client):
    login(client)
    with client.app_state.session_factory() as session:
        insert = text("INSERT INTO people (cpf, created_at, updated_at) VALUES (:cpf, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
        session.execute(insert, {"cpf": CPF})
        session.commit()
        assert pending(session, client.app_state.settings.key_ring())
    reencrypt(client.app_state.session_factory, client.app_state.store, client.app_state.settings.key_ring())
    cpf, index = raw_rows(client, "SELECT cpf, cpf_index FROM people")[0]
    assert cpf.startswith("enc2:") and index


@pytest.mark.parametrize("model", [Person, Document])
def test_models_index_cpf_on_assignment(model):
    configure_fields(KeyRing(generate_key()), "y" * 32)
    row = model(cpf=CPF)
    assert row.cpf_index == blind_index(CPF)


def test_storage_rewrite_skips_current_files(tmp_path):
    ring = KeyRing(generate_key())
    store = FileStore(tmp_path, ring)
    stored = store.save("originals", b"x")
    assert not store.rewrite(stored.relative_path)


def test_key_rotation_covers_records_and_cards(tmp_path, database_url):
    old_key = generate_key()
    with make_client(tmp_path, database_url, encryption_key=old_key) as client:
        add_user(client.app, "admin@exemplo.com")
        login(client, "admin@exemplo.com")
        client.put("/api/settings", json={"values": {"store_card_numbers": True}})
        client.app_state.ocr_engine = StaticBoxes(CARD_BOXES)
        image = encode_jpeg(photograph(render_rg_back()))
        files = [("pages", ("cartao.jpg", image, "image/jpeg"))]
        record = client.post("/api/records", data={"module": "cards"}, files=files).json()
        client.app_state.ocr_engine = StaticBoxes([TextBox("Relatório anual", 0.97, 40, 40, 900, 90)])
        files = [("pages", ("pagina.jpg", image, "image/jpeg"))]
        book = client.post("/api/records", data={"module": "books"}, files=files).json()
    new_key = generate_key()
    with make_client(tmp_path, database_url, encryption_key=new_key, encryption_old_keys=old_key) as client:
        ring = client.app_state.settings.key_ring()
        factory = client.app_state.session_factory
        with factory() as session:
            assert pending(session, ring)
        report = reencrypt(factory, client.app_state.store, ring)
        assert report.records == 2
        with factory() as session:
            assert not pending(session, ring)
            page = session.get(RecordPage, book["pages"][0]["id"])
            assert not ring.needs_rotation((tmp_path / "storage" / page.original_path).read_bytes())
    with make_client(tmp_path, database_url, encryption_key=new_key) as client:
        login(client, "admin@exemplo.com")
        assert client.get(f"/api/records/{record['id']}").json()["card"]["holder_name"] == "MARIA S OLIVEIRA"
        with client.app_state.session_factory() as session:
            assert session.get(CardDetail, record["id"]).full_number == "4111111111111111"
        assert client.get(f"/api/records/{book['id']}").json()["pages"][0]["text"]
