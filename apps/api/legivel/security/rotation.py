import base64
from dataclasses import dataclass

from sqlalchemy import Text, and_, exists, not_, or_, select, type_coerce
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from legivel.db.models import CardDetail, Document, DocumentImage, Person, ProcessingJob, Record, RecordPage, ReviewRevision
from legivel.security.crypto import FIELD_PREFIX, FILE_HEADER, KeyRing
from legivel.security.fields import blind_index
from legivel.services.settings import LOGO_PATH_KEY, stored_values
from legivel.storage.file_store import FileStore

PERSON_FIELDS = ("cpf",)
DOCUMENT_FIELDS = ("cpf", "rg_number", "cnh_register", "mrz_raw", "raw_text", "extra_fields")
RECORD_FIELDS = ("data",)
RECORD_PAGE_FIELDS = ("text", "layout")
CARD_FIELDS = ("holder_name", "full_number")
PROTECTED = (
    (Person, PERSON_FIELDS),
    (Document, DOCUMENT_FIELDS),
    (Record, RECORD_FIELDS),
    (RecordPage, RECORD_PAGE_FIELDS),
    (CardDetail, CARD_FIELDS),
    (ProcessingJob, ("payload",)),
    (ReviewRevision, ("before", "after")),
)
BATCH_SIZE = 200


@dataclass
class RotationReport:
    people: int = 0
    documents: int = 0
    records: int = 0
    files: int = 0


def rewrite_rows(session: Session, model, fields: tuple[str, ...]) -> int:
    key = model.__mapper__.primary_key[0]
    count = 0
    last_id = 0
    while True:
        rows = session.scalars(select(model).where(key > last_id).order_by(key).limit(BATCH_SIZE)).all()
        if not rows:
            return count
        for row in rows:
            for name in fields:
                if getattr(row, name) is not None:
                    flag_modified(row, name)
            if hasattr(row, "cpf_index"):
                row.cpf_index = blind_index(row.cpf)
            count += 1
        last_id = getattr(rows[-1], key.key)
        session.commit()


def current_prefix(ring: KeyRing) -> str:
    return FIELD_PREFIX + base64.urlsafe_b64encode(FILE_HEADER + ring.current_id).decode()


def pending(session: Session, ring: KeyRing | None) -> bool:
    checks = []
    for model, fields in PROTECTED:
        column_checks = [and_(model.cpf.is_not(None), model.cpf_index.is_(None))] if hasattr(model, "cpf_index") else []
        if ring is not None:
            prefix = current_prefix(ring)
            for name in fields:
                raw = type_coerce(getattr(model, name), Text)
                column_checks.append(and_(raw.is_not(None), not_(raw.startswith(prefix, autoescape=True))))
        if column_checks:
            checks.append(exists().where(or_(*column_checks)))
    return any(session.scalar(select(check)) for check in checks)


def reencrypt(factory: sessionmaker[Session], store: FileStore, ring: KeyRing | None) -> RotationReport:
    report = RotationReport()
    with factory() as session:
        report.people = rewrite_rows(session, Person, PERSON_FIELDS)
        report.documents = rewrite_rows(session, Document, DOCUMENT_FIELDS)
        report.records = rewrite_rows(session, Record, RECORD_FIELDS)
        rewrite_rows(session, RecordPage, RECORD_PAGE_FIELDS)
        rewrite_rows(session, CardDetail, CARD_FIELDS)
        rewrite_rows(session, ProcessingJob, ("payload",))
        rewrite_rows(session, ReviewRevision, ("before", "after"))
        if ring is None:
            return report
        paths = [
            path
            for model in (DocumentImage, RecordPage)
            for image in session.scalars(select(model))
            for path in (image.original_path, image.processed_path, image.thumbnail_path)
            if path
        ]
        paths.extend(path for job in session.scalars(select(ProcessingJob)) for path in job.payload.get("paths", []))
        logo = stored_values(session).get(LOGO_PATH_KEY)
        if logo:
            paths.append(logo)
    report.files = sum(1 for path in paths if store.rewrite(path))
    return report
