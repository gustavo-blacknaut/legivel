import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from legivel.db.base import utc_now
from legivel.db.models import CardDetail, DocumentStatus, Record, RecordPage
from legivel.imaging.preprocess import encode_processed, encode_thumbnail
from legivel.modules.base import ModuleOutput, OcrModule, ProcessingContext
from legivel.security.masking import mask_number
from legivel.services.audit import record as audit
from legivel.storage.file_store import FileStore

SEARCH_NUMBER = re.compile(r"\d[\d .\-/]{2,}\d")


@dataclass(frozen=True)
class CardPolicy:
    store_full_number: bool


def searchable(text: str) -> str:
    return SEARCH_NUMBER.sub(lambda match: mask_number(match.group(0)) or "", text)


def store_pages(store: FileStore, record: Record, module: OcrModule, output: ModuleOutput) -> None:
    for number, page in enumerate(output.pages, start=1):
        record_page = RecordPage(page_number=number, text=page.text, layout=page.layout, width=page.width, height=page.height)
        if module.keep_images:
            if page.original is not None:
                record_page.original_path = store.save("originals", page.original).relative_path
                record_page.original_mime = page.original_mime
            if page.processed is not None:
                record_page.processed_path = store.save("processed", encode_processed(page.processed)).relative_path
                record_page.thumbnail_path = store.save("thumbnails", encode_thumbnail(page.processed)).relative_path
        record.pages.append(record_page)


def apply_output(record: Record, module: OcrModule, output: ModuleOutput) -> None:
    record.kind = output.kind
    record.title = output.title
    record.language = output.language
    record.confidence = output.confidence
    record.data = {
        "fields": {name: field.value for name, field in output.fields.items()},
        "extracted": {name: field.value for name, field in output.fields.items()},
    }
    record.field_confidence = {name: field.confidence for name, field in output.fields.items()}
    record.issues = output.issues
    record.search_text = searchable(output.search_text)
    record.page_count = len(output.pages)
    record.status = DocumentStatus.PENDING_REVIEW


def apply_card(record: Record, output: ModuleOutput, policy: CardPolicy) -> None:
    card = output.card
    if card is None:
        return
    record.card = CardDetail(
        brand=card.brand,
        last4=card.last4,
        holder_name=card.holder_name,
        expiry=card.expiry,
        luhn_valid=card.luhn_valid,
        full_number=card.full_number if policy.store_full_number else None,
    )


def create_record(
    session: Session,
    store: FileStore,
    module: OcrModule,
    context: ProcessingContext,
    uploads: list[bytes],
    user_id: int | None,
    card_policy: CardPolicy,
    commit: bool = True,
) -> Record:
    output = module.process(context, uploads)
    record = Record(module=module.key, created_by=user_id, data={}, field_confidence={}, issues=[])
    apply_output(record, module, output)
    store_pages(store, record, module, output)
    apply_card(record, output, card_policy)
    session.add(record)
    session.flush()
    audit(session, user_id, "create", f"record:{module.key}", record.id)
    if commit:
        session.commit()
    return record


def update_record(session: Session, record: Record, module: OcrModule, values: dict[str, str], user_id: int | None) -> Record:
    editable = {spec.name for spec in module.fields_for(record.kind) if spec.kind not in ("readonly", "masked")}
    fields = dict(record.data.get("fields", {}))
    changed = []
    for name, value in values.items():
        if name in editable and (value or "").strip() != fields.get(name, ""):
            fields[name] = (value or "").strip()
            changed.append(name)
    record.data = {**record.data, "fields": fields}
    record.issues = module.validate(record.kind, fields)
    if "title" in changed and fields.get("title"):
        record.title = fields["title"]
    if record.card and "holder_name" in changed:
        record.card.holder_name = fields["holder_name"]
    if record.card and "expiry" in changed:
        record.card.expiry = fields["expiry"]
    record.status = DocumentStatus.REVIEWED
    record.updated_at = utc_now()
    audit(session, user_id, "review", f"record:{record.module}", record.id, ", ".join(changed) or "sem alterações")
    session.commit()
    return record


def delete_record(session: Session, store: FileStore, record: Record, user_id: int | None) -> None:
    for page in record.pages:
        for path in (page.original_path, page.processed_path, page.thumbnail_path):
            if path:
                store.delete(path)
    audit(session, user_id, "delete", f"record:{record.module}", record.id)
    session.delete(record)
    session.commit()
