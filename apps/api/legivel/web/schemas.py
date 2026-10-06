from datetime import datetime
from typing import Any

from pydantic import BaseModel

from legivel.db.models import Document, DocumentImage, DocumentStatus, ImageKind, Person
from legivel.parsers.base import DocumentParser
from legivel.parsers.registry import get_parser
from legivel.security.masking import is_sensitive, mask_number
from legivel.services.documents import document_values
from legivel.services.people import other_data
from legivel.validators.cpf import format_cpf

PERSONAL_FIELDS = {"full_name", "birth_date", "birthplace", "mother_name", "father_name"}


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
    masked: bool


class ReviewIn(BaseModel):
    values: dict[str, str]


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
    masked: bool
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
    user: str | None
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
        cpf=mask_number(format_cpf(document.cpf) if document.cpf else None),
        status=document.status,
        confidence=document.ocr_confidence_avg,
        processed_at=document.processed_at,
        thumbnail_url=f"/api/images/{page.id}/thumbnail" if page else None,
    )


def field_section(name: str, kind: str) -> str:
    if kind == "extra":
        return "extra"
    return "personal" if name in PERSONAL_FIELDS else "document"


def document_detail(document: Document, parser: DocumentParser, reveal: bool = False) -> DocumentDetail:
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
            value=shown(values.get(definition.name, ""), is_sensitive(definition.name, definition.kind) and not reveal),
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
        raw_text=(document.raw_text or "") if reveal else "",
        masked=not reveal,
        image_count=len(document.images),
        person_id=document.person_id,
    )


def shown(value: str, hide: bool) -> str:
    return (mask_number(value) or "") if hide else value


def person_status(person: Person) -> str | None:
    if not person.documents:
        return None
    if any(document.status == DocumentStatus.PENDING_REVIEW for document in person.documents):
        return DocumentStatus.PENDING_REVIEW
    return DocumentStatus.REVIEWED


def person_out(person: Person, reveal: bool = False) -> PersonOut:
    return PersonOut(
        id=person.id,
        full_name=person.full_name,
        cpf=person.cpf if reveal else mask_number(format_cpf(person.cpf) if person.cpf else None),
        birth_date=person.birth_date.strftime("%d/%m/%Y") if person.birth_date else None,
        status=person_status(person),
        doc_types=sorted({document.doc_type for document in person.documents}),
        documents=len(person.documents),
        images=sum(len(document.images) for document in person.documents),
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


def person_detail(person: Person, reveal: bool = False) -> PersonDetail:
    documents = sorted(person.documents, key=lambda document: document.processed_at, reverse=True)
    return PersonDetail(
        **person_out(person, reveal).model_dump(),
        masked=not reveal,
        mother_name=person.mother_name,
        father_name=person.father_name,
        birthplace=person.birthplace,
        document_list=[document_summary(document, get_parser(document.doc_type)) for document in documents],
        other_data=[
            OtherDataOut(
                label=item.label,
                value=shown(item.value, item.sensitive and not reveal),
                doc_type=item.doc_type,
                document_id=item.document_id,
            )
            for item in other_data(person)
        ],
    )


class SystemOut(BaseModel):
    ocr_engine: str
    ocr_device: str
    ocr_languages: str
    encrypted_storage: bool
    database: str
    smtp_configured: bool
    upload_max_mb: int
    upload_formats: list[str]
    retention_days: int
    ocr_status: dict[str, str | float | int | None]


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
    values: dict[str, Any]
    defaults: dict[str, Any]
    overridden: list[str]
    role_permissions: dict[str, list[str]]
    assignable_permissions: list[str]
    has_logo: bool


class SettingsIn(BaseModel):
    values: dict[str, Any]


class RolePermissionsIn(BaseModel):
    role_permissions: dict[str, list[str]]


class InstanceOut(BaseModel):
    name: str
    default_theme: str
    default_language: str
    timezone: str
    logo_url: str | None
    setup_required: bool
    smtp_configured: bool
    upload_max_mb: int
    upload_formats: list[str]
    password_min_length: int
    password_require_mixed: bool
    refresh_days: int


class ScanLinkIn(BaseModel):
    label: str | None = None
    hours: int | None = None


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
