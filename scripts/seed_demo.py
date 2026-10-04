import argparse
import random
from datetime import UTC, date, datetime, timedelta

import httpx

from app.config import get_settings
from app.db.models import Document, DocumentStatus, Person
from app.db.session import build_engine, build_session_factory
from app.validators.cpf import calculate_check_digits
from tests.synthetic import encode_jpeg, photograph, render_rg_back

FIRST_NAMES = (
    "ANA",
    "BRUNO",
    "CARLA",
    "DANIEL",
    "EDUARDA",
    "FELIPE",
    "GABRIELA",
    "HUGO",
    "ISABELA",
    "JOAO",
    "KARINA",
    "LUCAS",
    "MARIANA",
    "NATAN",
    "OLIVIA",
    "PEDRO",
    "RAFAELA",
    "SAMUEL",
    "TATIANA",
    "VINICIUS",
)
LAST_NAMES = (
    "ALMEIDA",
    "BARBOSA",
    "CARDOSO",
    "DIAS",
    "FERREIRA",
    "GOMES",
    "LIMA",
    "MARTINS",
    "NASCIMENTO",
    "OLIVEIRA",
    "PEREIRA",
    "RIBEIRO",
    "SANTOS",
    "SOUZA",
    "TEIXEIRA",
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


def seed_people(count: int, generator: random.Random) -> None:
    factory = build_session_factory(build_engine(get_settings().database_url))
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
                        ocr_engine="paddle",
                        ocr_confidence_avg=round(generator.uniform(0.72, 0.99), 3),
                        processed_at=created,
                        field_confidence={},
                        extra_fields={},
                    )
                )
            session.add(person)
        session.commit()


def seed_scanned(base_url: str, username: str, password: str, generator: random.Random, count: int) -> None:
    client = httpx.Client(base_url=base_url, headers={"X-Requested-With": "lince"}, timeout=600)
    client.post("/api/auth/login", json={"username": username, "password": password}).raise_for_status()
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
        client.post("/api/documents", files={"back": ("verso.jpg", image, "image/jpeg")}).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula uma instância de demonstração com dados fictícios")
    parser.add_argument("--people", type=int, default=2400)
    parser.add_argument("--scanned", type=int, default=3)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    arguments = parser.parse_args()
    generator = random.Random(2026)
    seed_people(arguments.people, generator)
    seed_scanned(arguments.base_url, arguments.username, arguments.password, generator, arguments.scanned)


if __name__ == "__main__":
    main()
