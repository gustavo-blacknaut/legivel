import argparse
import json
import os
import random
import tempfile
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

from legivel.auth.accounts import create_user
from legivel.config import load_settings
from legivel.db.models import Document
from legivel.db.session import build_engine, build_session_factory
from legivel.main import create_app
from legivel.ocr.factory import get_ocr_engine
from legivel.security.crypto import generate_key
from legivel.security.fields import configure_fields
from legivel.services.scan_links import create_link
from legivel.services.settings import load_runtime
from legivel.storage.file_store import FileStore
from scripts.seed_demo import seed_people, seed_readings, seed_scanned


def prepare(directory: Path, accounts: list[dict]) -> dict:
    os.environ.update(
        {
            "LEGIVEL_DATABASE_URL": os.environ.get("LEGIVEL_DATABASE_URL") or f"sqlite:///{directory / 'e2e.db'}",
            "LEGIVEL_STORAGE_DIR": str(directory / "storage"),
            "LEGIVEL_ENCRYPTION_KEY": generate_key(),
            "LEGIVEL_SECRET_KEY": generate_key(),
            "LEGIVEL_OCR_DEVICE": os.environ.get("LEGIVEL_OCR_DEVICE", "cpu"),
            "LEGIVEL_OCR_WARMUP": "false",
            "LEGIVEL_BACKGROUND_JOBS": "true",
        }
    )
    settings = load_settings(_env_file=None)
    config = Config("alembic.ini")
    config.attributes["database_url"] = settings.database_url
    command.upgrade(config, "head")
    factory = build_session_factory(build_engine(settings.database_url))
    store = FileStore(settings.storage_dir, settings.key_ring())
    configure_fields(settings.key_ring(), settings.secret_key)
    with factory() as session:
        runtime = load_runtime(session, settings)
        for account in accounts:
            create_user(session, account["email"], account["password"], runtime, account["role"], account["name"])
        session.commit()
    generator = random.Random(2026)
    seed_people(factory, 60, generator)
    engine = get_ocr_engine(settings.ocr_engine, settings.ocr_device, settings.ocr_model_dir, settings.ocr_languages)
    documents = seed_scanned(factory, store, engine, generator, 2)
    records = seed_readings(factory, store, engine)
    with factory() as session:
        link = create_link(session, None, "Admissão de teste", 48)
        person_id = session.get(Document, documents[0]).person_id
    return {
        "document_id": documents[0],
        "person_id": person_id,
        "scan_token": link.token,
        "record_id": records[0],
        "card_record_id": records[1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sobe a API com dados fictícios para os testes de ponta a ponta")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--accounts", required=True, help="JSON com as contas de teste")
    parser.add_argument("--state", required=True, help="arquivo onde gravar ids e tokens criados")
    arguments = parser.parse_args()
    accounts = json.loads(Path(arguments.accounts).read_text(encoding="utf-8"))
    directory = Path(tempfile.mkdtemp(prefix="legivel-e2e-"))
    state = prepare(directory, accounts)
    Path(arguments.state).parent.mkdir(parents=True, exist_ok=True)
    Path(arguments.state).write_text(json.dumps(state), encoding="utf-8")
    uvicorn.run(create_app(load_settings(_env_file=None)), host="127.0.0.1", port=arguments.port, log_level="warning")


if __name__ == "__main__":
    main()
