import pytest

from legivel.security.crypto import DecryptionError, EncryptionKeyError, KeyRing, decode_key, generate_key
from legivel.storage.file_store import FileStore

CONTENT = b"\x89PNG fake image bytes" * 100


@pytest.fixture
def store(tmp_path):
    return FileStore(tmp_path, KeyRing(generate_key()))


def test_round_trip_preserves_original_bytes(store):
    stored = store.save("originals", CONTENT)
    assert store.load(stored.relative_path) == CONTENT
    assert stored.size_bytes == len(CONTENT)
    assert len(stored.sha256) == 64


def test_file_on_disk_is_not_plaintext(store, tmp_path):
    stored = store.save("originals", CONTENT)
    on_disk = (tmp_path / stored.relative_path).read_bytes()
    assert CONTENT not in on_disk
    assert b"PNG" not in on_disk


def test_wrong_key_fails(tmp_path):
    stored = FileStore(tmp_path, KeyRing(generate_key())).save("originals", CONTENT)
    with pytest.raises(DecryptionError):
        FileStore(tmp_path, KeyRing(generate_key())).load(stored.relative_path)


def test_tampered_file_fails(store, tmp_path):
    stored = store.save("originals", CONTENT)
    path = tmp_path / stored.relative_path
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(DecryptionError):
        store.load(stored.relative_path)


def test_swapped_files_fail_due_to_bound_path(store, tmp_path):
    first = store.save("originals", b"first")
    second = store.save("originals", b"second")
    (tmp_path / first.relative_path).write_bytes((tmp_path / second.relative_path).read_bytes())
    with pytest.raises(DecryptionError):
        store.load(first.relative_path)


def test_delete_removes_file(store, tmp_path):
    stored = store.save("thumbnails", CONTENT)
    assert store.delete(stored.relative_path)
    assert not (tmp_path / stored.relative_path).exists()
    assert not store.delete(stored.relative_path)


def test_rejects_path_traversal_and_unknown_category(store):
    with pytest.raises(ValueError):
        store.load("../../etc/passwd")
    with pytest.raises(ValueError):
        store.save("anything", CONTENT)


@pytest.mark.parametrize("key", ["", "not-base64!!", "c2hvcnQ="])
def test_rejects_invalid_keys(key):
    with pytest.raises(EncryptionKeyError):
        decode_key(key)
