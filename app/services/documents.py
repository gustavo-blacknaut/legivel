import hashlib
from dataclasses import dataclass
from datetime import date

import cv2
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import AuditLog, Document, DocumentImage, DocumentStatus, ImageKind, ImageSide, Person
from app.imaging.crops import find_fingerprint, find_portrait, find_signature
from app.imaging.preprocess import (
    encode_processed,
    encode_thumbnail,
    load_image,
    prepare_image,
)
from app.ocr.base import OcrEngine, TextBox
from app.ocr.orientation import read_with_best_orientation
from app.parsers.base import ExtractedField, side_of, strip_accents
from app.parsers.classifier import classify
from app.parsers.common import repair_cpf_candidates
from app.parsers.registry import get_parser
from app.storage.encrypted_store import EncryptedFileStore
from app.validators.cpf import format_cpf, is_valid_cpf, normalize_cpf, only_digits
from app.validators.dates import format_brazilian_date, parse_brazilian_date

DOCUMENT_COLUMNS = (
    "full_name", "cpf", "birth_date", "mother_name", "father_name", "birthplace", "rg_number",
    "issuing_authority", "issue_date", "cnh_register", "cnh_category", "valid_until", "first_license_date", "mrz_raw",
)
DATE_COLUMNS = {"birth_date", "issue_date", "valid_until", "first_license_date"}
PERSON_COLUMNS = ("full_name", "birth_date", "mother_name", "father_name", "birthplace")
CPF_CROP_PADDING = 0.6
CPF_CROP_SCALE = 2.5
CORRECTED_CONFIDENCE_FACTOR = 0.85


@dataclass(frozen=True)
class UploadedSide:
    side: ImageSide
    content: bytes


@dataclass(frozen=True)
class SideReading:
    side: ImageSide
    image: np.ndarray
    boxes: list[TextBox]


def to_column_value(name: str, value: str | None):
    text = (value or "").strip()
    if not text:
        return None
    if name in DATE_COLUMNS:
        return parse_brazilian_date(text)
    if name == "cpf":
        digits = only_digits(text)
        return digits if len(digits) == 11 else None
    return text


def to_display_value(name: str, value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return format_brazilian_date(value)
    if name == "cpf" and len(value) == 11:
        return format_cpf(value)
    return str(value)


def apply_values(document: Document, values: dict[str, str]) -> None:
    extra = dict(document.extra_fields or {})
    unparsed = dict(extra.get("unparsed_values", {}))
    optional = dict(extra.get("values", {}))
    for name, raw in values.items():
        if name in DOCUMENT_COLUMNS:
            converted = to_column_value(name, raw)
            setattr(document, name, converted)
            unparsed.pop(name, None)
            if raw and converted is None:
                unparsed[name] = raw
        else:
            optional[name] = (raw or "").strip()
    extra["unparsed_values"] = unparsed
    extra["values"] = {name: value for name, value in optional.items() if value}
    document.extra_fields = extra


def document_values(document: Document) -> dict[str, str]:
    values = {name: to_display_value(name, getattr(document, name)) for name in DOCUMENT_COLUMNS}
    extra = document.extra_fields or {}
    values.update(extra.get("values", {}))
    values.update(extra.get("unparsed_values", {}))
    return values


def read_upload(engine: OcrEngine, uploaded: UploadedSide) -> SideReading:
    reading = read_with_best_orientation(engine, prepare_image(uploaded.content).ocr_image)
    side = ImageSide.BACK if uploaded.side == ImageSide.BACK else ImageSide.FRONT
    return SideReading(side, reading.image, reading.boxes)


def save_crop(store: EncryptedFileStore, document: Document, side: str, kind: ImageKind, crop: np.ndarray | None) -> None:
    if crop is None:
        return
    content = encode_processed(crop)
    document.images.append(
        DocumentImage(
            side=side,
            kind=kind,
            original_path=store.save("processed", content).relative_path,
            thumbnail_path=store.save("thumbnails", encode_thumbnail(crop)).relative_path,
            original_mime="image/jpeg",
            sha256=hashlib.sha256(content).hexdigest(),
            width=crop.shape[1],
            height=crop.shape[0],
        )
    )


def save_crops(store: EncryptedFileStore, document: Document, readings: list[SideReading]) -> None:
    portrait_saved = False
    for reading in readings:
        if not portrait_saved:
            portrait = find_portrait(reading.image)
            save_crop(store, document, reading.side, ImageKind.PORTRAIT, portrait)
            portrait_saved = portrait is not None
        save_crop(store, document, reading.side, ImageKind.SIGNATURE, find_signature(reading.image, reading.boxes))
        save_crop(store, document, reading.side, ImageKind.FINGERPRINT, find_fingerprint(reading.image, reading.boxes))


def unique_valid_cpf(texts: list[str]) -> str | None:
    candidates = {candidate for text in texts for candidate in repair_cpf_candidates(text)}
    return candidates.pop() if len(candidates) == 1 else None


def reread_region(engine: OcrEngine, image: np.ndarray, box: TextBox) -> list[str]:
    padding_x = (box.x1 - box.x0) * CPF_CROP_PADDING
    padding_y = box.height * CPF_CROP_PADDING
    height, width = image.shape[:2]
    x0, y0 = max(int(box.x0 - padding_x), 0), max(int(box.y0 - padding_y), 0)
    x1, y1 = min(int(box.x1 + padding_x), width), min(int(box.y1 + padding_y), height)
    if x1 - x0 < 10 or y1 - y0 < 10:
        return []
    crop = cv2.resize(image[y0:y1, x0:x1], None, fx=CPF_CROP_SCALE, fy=CPF_CROP_SCALE, interpolation=cv2.INTER_CUBIC)
    sharpened = cv2.addWeighted(crop, 1.6, cv2.GaussianBlur(crop, (0, 0), 3), -0.6, 0)
    texts = []
    for variant in (crop, sharpened):
        boxes = engine.read(variant)
        texts.extend(box.text for box in boxes)
        texts.append(" ".join(box.text for box in sorted(boxes, key=lambda item: item.x0)))
    return texts


def verify_cpf(engine: OcrEngine, readings: list[SideReading], fields: dict[str, ExtractedField]) -> str | None:
    current = fields.get("cpf")
    if current and is_valid_cpf(current.value):
        return None
    texts = [current.box.text] if current and current.box else []
    repaired = unique_valid_cpf(texts)
    if repaired is None and current and current.box:
        side_index, box = side_of(current.box)
        if side_index < len(readings):
            repaired = unique_valid_cpf(reread_region(engine, readings[side_index].image, box))
    if repaired is None and current is None:
        repaired = unique_valid_cpf([box.text for reading in readings for box in reading.boxes])
    if repaired is None:
        return "cpf_unverified" if current else None
    confidence = (current.confidence or 1.0) * CORRECTED_CONFIDENCE_FACTOR if current else 0.7
    fields["cpf"] = ExtractedField(format_cpf(repaired), confidence, current.box if current else None)
    return "cpf_corrected"


def apply_extraction(document: Document, engine: OcrEngine, readings: list[SideReading], detected: bool = False) -> None:
    front = [box for reading in readings if reading.side == ImageSide.FRONT for box in reading.boxes]
    back = [box for reading in readings if reading.side == ImageSide.BACK for box in reading.boxes]
    ordered = sorted(readings, key=lambda reading: reading.side != ImageSide.FRONT)
    parser = get_parser(document.doc_type)
    result = parser.parse(front, back)
    cpf_status = verify_cpf(engine, ordered, result.fields)
    if cpf_status == "cpf_corrected":
        result.issues = parser.validate(result.values())
    document.extra_fields = {}
    for name in DOCUMENT_COLUMNS:
        setattr(document, name, None)
    apply_values(document, result.values())
    document.field_confidence = {name: field.confidence for name, field in result.fields.items()}
    document.extra_fields = {
        **document.extra_fields,
        "extracted": result.values(),
        "issues": result.issues,
        "notes": [note for note in (cpf_status, "type_detected" if detected else None) if note],
    }
    all_boxes = front + back
    document.ocr_confidence_avg = sum(box.confidence for box in all_boxes) / len(all_boxes) if all_boxes else None
    document.raw_text = result.raw_text
    document.ocr_engine = engine.name
    document.processed_at = utc_now()
    document.status = DocumentStatus.PENDING_REVIEW
    document.reviewed_manually = False
    document.reviewed_at = None


def store_page(store: EncryptedFileStore, document: Document, uploaded: UploadedSide, reading: SideReading) -> None:
    original = store.save("originals", uploaded.content)
    image, mime = load_image(uploaded.content)
    document.images.append(
        DocumentImage(
            side=reading.side,
            kind=ImageKind.PAGE,
            original_path=original.relative_path,
            processed_path=store.save("processed", encode_processed(reading.image)).relative_path,
            thumbnail_path=store.save("thumbnails", encode_thumbnail(reading.image)).relative_path,
            original_mime=mime,
            sha256=original.sha256,
            width=image.width,
            height=image.height,
        )
    )


def resolve_type(requested: str | None, readings: list[SideReading]) -> tuple[str, bool]:
    if requested:
        get_parser(requested)
        return requested, False
    classification = classify([box for reading in readings for box in reading.boxes])
    return classification.doc_type, classification.detected


def process_document(
    session: Session,
    store: EncryptedFileStore,
    engine: OcrEngine,
    doc_type: str | None,
    sides: list[UploadedSide],
    user_id: int | None = None,
) -> Document:
    if doc_type:
        get_parser(doc_type)
    readings = [read_upload(engine, uploaded) for uploaded in sides]
    resolved_type, detected = resolve_type(doc_type, readings)
    document = Document(doc_type=resolved_type, ocr_engine=engine.name, created_by=user_id, field_confidence={}, extra_fields={})
    for uploaded, reading in zip(sides, readings, strict=True):
        store_page(store, document, uploaded, reading)
    save_crops(store, document, readings)
    apply_extraction(document, engine, readings, detected)
    link_person_by_cpf(session, document)
    session.add(document)
    session.flush()
    session.add(AuditLog(user_id=user_id, action="create", entity="document", entity_id=document.id))
    session.commit()
    return document


def delete_image_files(store: EncryptedFileStore, image: DocumentImage) -> None:
    for path in (image.original_path, image.processed_path, image.thumbnail_path):
        if path:
            store.delete(path)


def reprocess_document(
    session: Session,
    store: EncryptedFileStore,
    engine: OcrEngine,
    document: Document,
    user_id: int | None = None,
    doc_type: str | None = None,
) -> Document:
    readings: list[SideReading] = []
    for image in list(document.images):
        if image.kind != ImageKind.PAGE:
            delete_image_files(store, image)
            document.images.remove(image)
            continue
        reading = read_upload(engine, UploadedSide(ImageSide(image.side), store.load(image.original_path)))
        readings.append(reading)
        for path in (image.processed_path, image.thumbnail_path):
            if path:
                store.delete(path)
        image.side = reading.side
        image.processed_path = store.save("processed", encode_processed(reading.image)).relative_path
        image.thumbnail_path = store.save("thumbnails", encode_thumbnail(reading.image)).relative_path
    document.doc_type, detected = resolve_type(doc_type, readings)
    save_crops(store, document, readings)
    apply_extraction(document, engine, readings, detected)
    link_person_by_cpf(session, document)
    session.add(AuditLog(user_id=user_id, action="reprocess", entity="document", entity_id=document.id))
    session.commit()
    return document


def review_document(session: Session, document: Document, values: dict[str, str], user_id: int | None = None) -> Document:
    parser = get_parser(document.doc_type)
    extracted = (document.extra_fields or {}).get("extracted", {})
    apply_values(document, {name: values.get(name, "") for name in parser.field_names if name in values})
    current = document_values(document)
    document.extra_fields = {**document.extra_fields, "issues": parser.validate(current)}
    document.reviewed_manually = any(
        (extracted.get(name) or "") != (current.get(name) or "") for name in parser.field_names
    )
    document.status = DocumentStatus.REVIEWED
    document.reviewed_at = utc_now()
    document.person = upsert_person(session, document)
    session.add(AuditLog(user_id=user_id, action="review", entity="document", entity_id=document.id))
    session.commit()
    return document


def upsert_person(session: Session, document: Document, overwrite: bool = True) -> Person:
    cpf = normalize_cpf(document.cpf or "")
    person = document.person
    if cpf:
        existing = session.scalar(select(Person).where(Person.cpf == cpf))
        if existing is not None:
            person = existing
    if person is None:
        person = Person()
        session.add(person)
    if cpf and person.cpf is None:
        person.cpf = cpf
    for name in PERSON_COLUMNS:
        value = getattr(document, name)
        if isinstance(value, str):
            value = strip_accents(value)
        if value and (overwrite or getattr(person, name) is None):
            setattr(person, name, value)
    return person


def delete_document(session: Session, store: EncryptedFileStore, document: Document, user_id: int | None = None) -> None:
    for image in document.images:
        delete_image_files(store, image)
    person = document.person
    session.add(AuditLog(user_id=user_id, action="delete", entity="document", entity_id=document.id))
    session.delete(document)
    session.flush()
    if person is not None and not session.scalar(select(func.count()).where(Document.person_id == person.id)):
        session.delete(person)
    session.commit()


def delete_person(session: Session, store: EncryptedFileStore, person: Person, user_id: int | None = None) -> None:
    for document in list(person.documents):
        for image in document.images:
            delete_image_files(store, image)
    session.add(AuditLog(user_id=user_id, action="delete", entity="person", entity_id=person.id))
    session.delete(person)
    session.commit()



def link_person_by_cpf(session: Session, document: Document) -> None:
    if normalize_cpf(document.cpf or ""):
        document.person = upsert_person(session, document, overwrite=False)
