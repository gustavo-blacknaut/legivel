from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import Document, DocumentStatus, Person
from app.parsers.base import strip_accents
from app.parsers.registry import get_parser
from app.services.audit import record
from app.services.documents import document_values
from app.validators.cpf import is_valid_cpf, only_digits
from app.validators.dates import format_brazilian_date, parse_brazilian_date

TEXT_FIELDS = ("full_name", "mother_name", "father_name", "birthplace")
PERSON_FIELDS = (*TEXT_FIELDS, "birth_date", "cpf")
FIELD_LABELS = {
    "full_name": "Nome",
    "mother_name": "Mãe",
    "father_name": "Pai",
    "birthplace": "Naturalidade",
    "birth_date": "Nascimento",
    "cpf": "CPF",
}
MINIMUM_BIRTH_YEAR = 1900


class PersonUpdateError(ValueError):
    pass


@dataclass(frozen=True)
class OtherDataItem:
    label: str
    value: str
    doc_type: str
    document_id: int


@dataclass(frozen=True)
class VerificationResult:
    changes: list[str]
    problems: list[str]


def clean_text(value: str | None) -> str | None:
    text = " ".join(strip_accents(value or "").upper().split())
    return text or None


def update_person(session: Session, person: Person, values: dict[str, str | None], user_id: int | None) -> Person:
    changed = []
    for name in TEXT_FIELDS:
        if name in values:
            cleaned = clean_text(values[name])
            if cleaned != getattr(person, name):
                setattr(person, name, cleaned)
                changed.append(FIELD_LABELS[name])
    if "birth_date" in values:
        raw = (values["birth_date"] or "").strip()
        parsed = parse_brazilian_date(raw) if raw else None
        if raw and parsed is None:
            raise PersonUpdateError("Data de nascimento inválida. Use dd/mm/aaaa.")
        if parsed != person.birth_date:
            person.birth_date = parsed
            changed.append(FIELD_LABELS["birth_date"])
    if "cpf" in values:
        digits = only_digits(values["cpf"] or "") or None
        if digits and not is_valid_cpf(digits):
            raise PersonUpdateError("CPF inválido: o dígito verificador não confere.")
        if digits and digits != person.cpf:
            owner = session.scalar(select(Person).where(Person.cpf == digits, Person.id != person.id))
            if owner is not None:
                raise PersonUpdateError("Este CPF já pertence a outra pessoa do cadastro.")
        if digits != person.cpf:
            person.cpf = digits
            changed.append(FIELD_LABELS["cpf"])
    if changed:
        person.updated_at = utc_now()
        record(session, user_id, "update", "person", person.id, ", ".join(changed))
    session.commit()
    return person


def documents_by_priority(person: Person) -> list[Document]:
    return sorted(
        person.documents,
        key=lambda document: (document.status == DocumentStatus.REVIEWED, document.processed_at),
        reverse=True,
    )


def verify_person(session: Session, person: Person, user_id: int | None) -> VerificationResult:
    changes: list[str] = []
    problems: list[str] = []
    for name in TEXT_FIELDS:
        current = getattr(person, name)
        cleaned = clean_text(current)
        if cleaned != current:
            setattr(person, name, cleaned)
            changes.append(f"{FIELD_LABELS[name]}: acentos e espaços corrigidos")
    for name in (*TEXT_FIELDS, "birth_date"):
        if getattr(person, name):
            continue
        for document in documents_by_priority(person):
            value = getattr(document, name)
            if value:
                setattr(person, name, clean_text(value) if isinstance(value, str) else value)
                changes.append(f"{FIELD_LABELS[name]}: preenchido a partir do {document.doc_type.upper()} #{document.id}")
                break
    if not person.cpf:
        problems.append("CPF não informado")
    elif not is_valid_cpf(person.cpf):
        problems.append("CPF com dígito verificador inválido")
    if not person.full_name:
        problems.append("Nome não informado")
    if person.birth_date is None:
        problems.append("Data de nascimento não informada")
    elif person.birth_date.year < MINIMUM_BIRTH_YEAR or person.birth_date > date.today():
        problems.append("Data de nascimento fora do intervalo plausível")
    for document in person.documents:
        if document.cpf and person.cpf and document.cpf != person.cpf:
            problems.append(f"{document.doc_type.upper()} #{document.id} tem CPF diferente do cadastro")
        if document.birth_date and person.birth_date and document.birth_date != person.birth_date:
            problems.append(
                f"{document.doc_type.upper()} #{document.id} tem nascimento {format_brazilian_date(document.birth_date)}"
            )
    pending = sum(1 for document in person.documents if document.status == DocumentStatus.PENDING_REVIEW)
    if pending:
        problems.append(f"{pending} documento(s) aguardando revisão")
    if changes:
        person.updated_at = utc_now()
    record(session, user_id, "verify", "person", person.id, f"{len(changes)} correções, {len(problems)} pendências")
    session.commit()
    return VerificationResult(changes, problems)


def other_data(person: Person) -> list[OtherDataItem]:
    seen: set[tuple[str, str]] = set()
    items: list[OtherDataItem] = []
    for document in documents_by_priority(person):
        parser = get_parser(document.doc_type)
        values = document_values(document)
        for definition in parser.field_definitions:
            if definition.name in PERSON_FIELDS or definition.name == "mrz_raw":
                continue
            value = (values.get(definition.name) or "").strip()
            key = (definition.label, value)
            if not value or key in seen:
                continue
            seen.add(key)
            items.append(OtherDataItem(definition.label, value, document.doc_type, document.id))
    return items
