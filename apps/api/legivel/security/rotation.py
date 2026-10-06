import base64
from dataclasses import dataclass

from sqlalchemy import Text, and_, exists, not_, or_, select, type_coerce
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from legivel.db.models import Document, DocumentImage, Person
from legivel.security.crypto import FIELD_PREFIX, FILE_HEADER, KeyRing
from legivel.security.fields import blind_index
from legivel.services.settings import LOGO_PATH_KEY, stored_values
from legivel.storage.file_store import FileStore

PERSON_FIELDS = ("cpf",)
DOCUMENT_FIELDS = ("cpf", "rg_number", "cnh_register", "mrz_raw", "raw_text", "extra_fields")
BATCH_SIZE = 200


@dataclass
class RotationReport:
    people: int = 0
    documents: int = 0
    files: int = 0


def rewrite_rows(session: Session, model, fields: tuple[str, ...]) -> int:
    count = 0
    last_id = 0
    while True:
        rows = session.scalars(select(model).where(model.id > last_id).order_by(model.id).limit(BATCH_SIZE)).all()
        if not rows:
            return count
        for row in rows:
            for name in fields:
                if getattr(row, name) is not None:
                    flag_modified(row, name)
            if hasattr(row, "cpf_index"):
                row.cpf_index = blind_index(row.cpf)
            count += 1
        last_id = rows[-1].id
        session.commit()


def current_prefix(ring: KeyRing) -> str:
    return FIELD_PREFIX + base64.urlsafe_b64encode(FILE_HEADER + ring.current_id).decode()


def pending(session: Session, ring: KeyRing | None) -> bool:
    checks = []
    for model, fields in ((Person, PERSON_FIELDS), (Document, DOCUMENT_FIELDS)):
        column_checks = [and_(model.cpf.is_not(None), model.cpf_index.is_(None))]
        if ring is not None:
            prefix = current_prefix(ring)
            for name in fields:
                raw = type_coerce(getattr(model, name), Text)
                column_checks.append(and_(raw.is_not(None), not_(raw.startswith(prefix, autoescape=True))))
        checks.append(exists().where(or_(*column_checks)))
    return any(session.scalar(select(check)) for check in checks)


def reencrypt(factory: sessionmaker[Session], store: FileStore, ring: KeyRing | None) -> RotationReport:
    report = RotationReport()
    with factory() as session:
        report.people = rewrite_rows(session, Person, PERSON_FIELDS)
        report.documents = rewrite_rows(session, Document, DOCUMENT_FIELDS)
        if ring is None:
            return report
        paths = [
            path
            for image in session.scalars(select(DocumentImage))
            for path in (image.original_path, image.processed_path, image.thumbnail_path)
            if path
        ]
        logo = stored_values(session).get(LOGO_PATH_KEY)
        if logo:
            paths.append(logo)
    report.files = sum(1 for path in paths if store.rewrite(path))
    return report
