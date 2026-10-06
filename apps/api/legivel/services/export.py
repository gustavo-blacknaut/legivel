from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from legivel.db.base import utc_now
from legivel.db.models import AuditLog, Document, DocumentImage, Person
from legivel.services.documents import document_values

EXPORT_FORMAT = "legivel.person"
EXPORT_VERSION = 1


def iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def image_entry(image: DocumentImage) -> dict:
    return {
        "id": image.id,
        "side": image.side,
        "kind": image.kind,
        "mime": image.original_mime,
        "sha256": image.sha256,
        "width": image.width,
        "height": image.height,
        "created_at": iso(image.created_at),
    }


def document_entry(document: Document) -> dict:
    return {
        "id": document.id,
        "type": document.doc_type,
        "status": document.status,
        "reviewed_manually": document.reviewed_manually,
        "processed_at": iso(document.processed_at),
        "reviewed_at": iso(document.reviewed_at),
        "ocr_engine": document.ocr_engine,
        "ocr_confidence": document.ocr_confidence_avg,
        "fields": {name: value for name, value in document_values(document).items() if value},
        "field_confidence": document.field_confidence or {},
        "ocr_text": document.raw_text,
        "images": [image_entry(image) for image in sorted(document.images, key=lambda image: image.id)],
    }


def access_history(session: Session, person: Person) -> list[dict]:
    document_ids = [document.id for document in person.documents]
    condition = (AuditLog.entity == "person") & (AuditLog.entity_id == person.id)
    if document_ids:
        condition = or_(condition, (AuditLog.entity == "document") & AuditLog.entity_id.in_(document_ids))
    entries = session.scalars(select(AuditLog).where(condition).order_by(AuditLog.occurred_at, AuditLog.id))
    return [
        {"occurred_at": iso(entry.occurred_at), "action": entry.action, "entity": entry.entity, "entity_id": entry.entity_id}
        for entry in entries
    ]


def export_person(session: Session, person: Person) -> dict:
    documents = sorted(person.documents, key=lambda document: document.processed_at)
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": iso(utc_now()),
        "person": {
            "id": person.id,
            "full_name": person.full_name,
            "cpf": person.cpf,
            "birth_date": iso(person.birth_date),
            "birthplace": person.birthplace,
            "mother_name": person.mother_name,
            "father_name": person.father_name,
            "created_at": iso(person.created_at),
            "updated_at": iso(person.updated_at),
        },
        "documents": [document_entry(document) for document in documents],
        "access_history": access_history(session, person),
    }
