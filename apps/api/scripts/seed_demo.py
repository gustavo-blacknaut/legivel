import argparse
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from legivel.config import get_settings
from legivel.db.models import Document, DocumentStatus, ImageSide, Person, Record
from legivel.db.session import build_engine, build_session_factory
from legivel.modules.base import ProcessingContext
from legivel.modules.registry import get_module
from legivel.ocr.base import OcrEngine
from legivel.security.fields import configure_fields
from legivel.services.documents import UploadedSide, process_document
from legivel.services.records import CardPolicy, create_record
from legivel.storage.file_store import FileStore
from legivel.validators.cpf import calculate_check_digits
from tests.synthetic import encode_jpeg, photograph, render_card, render_rg_back, render_two_columns

FIRST_NAMES = (
    "ANA", "BRUNO", "CARLA", "DANIEL", "EDUARDA", "FELIPE", "GABRIELA", "HUGO", "ISABELA", "JOAO", "KARINA",
    "LUCAS", "MARIANA", "NATAN", "OLIVIA", "PEDRO", "RAFAELA", "SAMUEL", "TATIANA", "VINICIUS",
)
LAST_NAMES = (
    "ALMEIDA", "BARBOSA", "CARDOSO", "DIAS", "FERREIRA", "GOMES", "LIMA", "MARTINS", "NASCIMENTO", "OLIVEIRA",
    "PEREIRA", "RIBEIRO", "SANTOS", "SOUZA", "TEIXEIRA",
)
STATUS_WEIGHTS = (DocumentStatus.REVIEWED, DocumentStatus.REVIEWED, DocumentStatus.PENDING_REVIEW)
CITIES = ("CAMPINAS-SP", "BELO HORIZONTE-MG", "NOVA LIMA-MG", "CURITIBA-PR", "RECIFE-PE", "SALVADOR-BA")


def fictitious_cpf(generator: random.Random) -> str:
    base = "".join(str(generator.randint(0, 9)) for _ in range(9))
    return base + calculate_check_digits(base)


def fictitious_rg(generator: random.Random) -> str:
    return f"{generator.randint(10, 59)}.{generator.randint(100, 999)}.{generator.randint(100, 999)}-{generator.randint(0, 9)}"


def fictitious_name(generator: random.Random) -> str:
    return f"{generator.choice(FIRST_NAMES)} {generator.choice(LAST_NAMES)} {generator.choice(LAST_NAMES)}"


def seed_people(factory: sessionmaker[Session], count: int, generator: random.Random) -> None:
    start = datetime(2025, 1, 1, 9, tzinfo=UTC)
    with factory() as session:
        for index in range(count):
            created = start + timedelta(hours=index * 3, minutes=generator.randint(0, 59))
            name = fictitious_name(generator)
            cpf = fictitious_cpf(generator)
            person = Person(
                full_name=name,
                cpf=cpf,
                birth_date=date(generator.randint(1950, 2005), generator.randint(1, 12), generator.randint(1, 28)),
                birthplace=generator.choice(CITIES),
                created_at=created,
                updated_at=created,
            )
            for doc_type in generator.sample(("rg", "cnh", "cpf"), generator.choice((1, 1, 2))):
                person.documents.append(
                    Document(
                        doc_type=doc_type,
                        status=generator.choice(STATUS_WEIGHTS),
                        full_name=name,
                        cpf=cpf,
                        ocr_engine="rapidocr",
                        ocr_confidence_avg=round(generator.uniform(0.72, 0.99), 3),
                        processed_at=created,
                        field_confidence={},
                        extra_fields={},
                    )
                )
            session.add(person)
        session.commit()


def seed_scanned(
    factory: sessionmaker[Session], store: FileStore, engine: OcrEngine, generator: random.Random, count: int
) -> list[int]:
    created = []
    for index in range(count):
        cpf = fictitious_cpf(generator)
        values = {
            "rg_number": fictitious_rg(generator),
            "issue_date": "12/06/2015",
            "full_name": fictitious_name(generator),
            "father_name": fictitious_name(generator),
            "mother_name": fictitious_name(generator),
            "birthplace": generator.choice(CITIES),
            "birth_date": f"{generator.randint(1, 28):02d}/{generator.randint(1, 12):02d}/{generator.randint(1960, 2000)}",
            "cpf": f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}",
            "issuing_authority": "SSP/SP",
        }
        image = encode_jpeg(photograph(render_rg_back(values), angle_degrees=4 + index * 3))
        with factory() as session:
            document = process_document(session, store, engine, None, [UploadedSide(ImageSide.BACK, image)])
            created.append(document.id)
    return created


def seed_readings(factory: sessionmaker[Session], store: FileStore, engine: OcrEngine) -> list[int]:
    context = ProcessingContext(engine_for_pack=lambda pack: engine, enabled_languages=["pt", "en", "es"])
    created = []
    for module, image in (("books", render_two_columns()), ("cards", render_card())):
        with factory() as session:
            record: Record = create_record(session, store, get_module(module), context, [image], None, CardPolicy(False))
            created.append(record.id)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula uma instância de demonstração com dados fictícios")
    parser.add_argument("--people", type=int, default=2400)
    parser.add_argument("--scanned", type=int, default=3)
    arguments = parser.parse_args()
    from legivel.ocr.factory import get_ocr_engine

    settings = get_settings()
    factory = build_session_factory(build_engine(settings.database_url))
    store = FileStore(settings.storage_dir, settings.key_ring())
    configure_fields(settings.key_ring(), settings.secret_key)
    generator = random.Random(2026)
    seed_people(factory, arguments.people, generator)
    if arguments.scanned:
        engine = get_ocr_engine(settings.ocr_engine, settings.ocr_device, settings.ocr_model_dir, settings.ocr_languages)
        seed_scanned(factory, store, engine, generator, arguments.scanned)
        seed_readings(factory, store, engine)
    print(f"{arguments.people} pessoas fictícias e {arguments.scanned} documento(s) lidos pelo OCR")


if __name__ == "__main__":
    main()
