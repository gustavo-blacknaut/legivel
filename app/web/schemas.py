from datetime import datetime

from pydantic import BaseModel

from app.db.models import Document, DocumentImage, DocumentStatus, ImageKind, Person
from app.parsers.base import DocumentParser
from app.parsers.registry import get_parser
from app.services.documents import document_values
from app.services.people import other_data

PERSONAL_FIELDS = {"full_name", "birth_date", "birthplace", "mother_name", "father_name"}


class Credentials(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str


class DocumentTypeOut(BaseModel):
    doc_type: str
    display_name: str


class ImageOut(BaseModel):
    id: int
    side: str
    kind: str
    thumbnail_url: str
    full_url: str
    original_url: str


class FieldOut(BaseModel):
    name: str
    label: str
    kind: str
    section: str
    value: str
    confidence: float | None
    issues: list[str]


class DocumentSummary(BaseModel):
    id: int
    doc_type: str
    type_name: str
    full_name: str | None
    cpf: str | None
    status: str
    confidence: float | None
    processed_at: datetime
    thumbnail_url: str | None


class DocumentDetail(DocumentSummary):
    reviewed_manually: bool
    type_detected: bool
    notes: list[str]
    fields: list[FieldOut]
    pages: list[ImageOut]
    crops: list[ImageOut]
    raw_text: str
    image_count: int
    person_id: int | None


class ReviewIn(BaseModel):
    values: dict[str, str]


class ReprocessIn(BaseModel):
    doc_type: str | None = None


class StatsOut(BaseModel):
    documents: int
    pending: int
    people: int


class OverviewOut(BaseModel):
    stats: StatsOut
    documents: list[DocumentSummary]


class PersonOut(BaseModel):
    id: int
    full_name: str | None
    cpf: str | None
    birth_date: str | None
    status: str | None
    doc_types: list[str]
    documents: int
    images: int
    created_at: datetime
    updated_at: datetime


class PersonDetail(PersonOut):
    mother_name: str | None
    father_name: str | None
    birthplace: str | None
    document_list: list[DocumentSummary]
    other_data: list["OtherDataOut"]


class PageOut[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class AuditOut(BaseModel):
    id: int
    occurred_at: datetime
    username: str | None
    action: str
    entity: str
    entity_id: int | None
    details: str | None
    ip_address: str | None


def image_out(image: DocumentImage) -> ImageOut:
    base = f"/api/images/{image.id}"
    full = f"{base}/processed" if image.processed_path else f"{base}/original"
    return ImageOut(
        id=image.id,
        side=image.side,
        kind=image.kind,
        thumbnail_url=f"{base}/thumbnail",
        full_url=full,
        original_url=f"{base}/original",
    )


def first_page(document: Document) -> DocumentImage | None:
    pages = [image for image in document.images if image.kind == ImageKind.PAGE]
    return pages[0] if pages else None


def document_summary(document: Document, parser: DocumentParser) -> DocumentSummary:
    page = first_page(document)
    return DocumentSummary(
        id=document.id,
        doc_type=document.doc_type,
        type_name=parser.display_name,
        full_name=document.full_name,
        cpf=document.cpf,
        status=document.status,
        confidence=document.ocr_confidence_avg,
        processed_at=document.processed_at,
        thumbnail_url=f"/api/images/{page.id}/thumbnail" if page else None,
    )


def field_section(name: str, kind: str) -> str:
    if kind == "extra":
        return "extra"
    return "personal" if name in PERSONAL_FIELDS else "document"


def document_detail(document: Document, parser: DocumentParser) -> DocumentDetail:
    extra = document.extra_fields or {}
    values = document_values(document)
    confidence = document.field_confidence or {}
    issues: dict[str, list[str]] = {}
    for issue in extra.get("issues", []):
        issues.setdefault(issue["field"], []).append(issue["message"])
    fields = [
        FieldOut(
            name=definition.name,
            label=definition.label,
            kind=definition.kind,
            section=field_section(definition.name, definition.kind),
            value=values.get(definition.name, ""),
            confidence=confidence.get(definition.name) if values.get(definition.name) else None,
            issues=issues.get(definition.name, []),
        )
        for definition in parser.field_definitions
    ]
    notes = extra.get("notes", [])
    return DocumentDetail(
        **document_summary(document, parser).model_dump(),
        reviewed_manually=document.reviewed_manually,
        type_detected="type_detected" in notes,
        notes=notes,
        fields=fields,
        pages=[image_out(image) for image in document.images if image.kind == ImageKind.PAGE],
        crops=[image_out(image) for image in document.images if image.kind != ImageKind.PAGE],
        raw_text=document.raw_text or "",
        image_count=len(document.images),
        person_id=document.person_id,
    )


def person_status(person: Person) -> str | None:
    if not person.documents:
        return None
    if any(document.status == DocumentStatus.PENDING_REVIEW for document in person.documents):
        return DocumentStatus.PENDING_REVIEW
    return DocumentStatus.REVIEWED


def person_out(person: Person) -> PersonOut:
    return PersonOut(
        id=person.id,
        full_name=person.full_name,
        cpf=person.cpf,
        birth_date=person.birth_date.strftime("%d/%m/%Y") if person.birth_date else None,
        status=person_status(person),
        doc_types=sorted({document.doc_type for document in person.documents}),
        documents=len(person.documents),
        images=sum(len(document.images) for document in person.documents),
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


def person_detail(person: Person) -> PersonDetail:
    documents = sorted(person.documents, key=lambda document: document.processed_at, reverse=True)
    return PersonDetail(
        **person_out(person).model_dump(),
        mother_name=person.mother_name,
        father_name=person.father_name,
        birthplace=person.birthplace,
        document_list=[document_summary(document, get_parser(document.doc_type)) for document in documents],
        other_data=[OtherDataOut(**vars(item)) for item in other_data(person)],
    )


class SystemOut(BaseModel):
    ocr_engine: str
    ocr_device: str
    encrypted_storage: bool
    max_upload_mb: int


class OtherDataOut(BaseModel):
    label: str
    value: str
    doc_type: str
    document_id: int


class PersonUpdateIn(BaseModel):
    values: dict[str, str | None]


class VerificationOut(BaseModel):
    changes: list[str]
    problems: list[str]
    person: "PersonDetail"


class SettingsOut(BaseModel):
    timezone: str


class SettingsIn(BaseModel):
    timezone: str


class SessionOut(BaseModel):
    id: int
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class ScanLinkIn(BaseModel):
    label: str | None = None
    hours: int = 48


class ScanLinkOut(BaseModel):
    id: int
    label: str | None
    state: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    document_id: int | None


class ScanLinkCreated(ScanLinkOut):
    token: str


class PublicLinkOut(BaseModel):
    label: str | None
    state: str
    expires_at: datetime
