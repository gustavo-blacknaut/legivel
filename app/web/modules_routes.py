import json
import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Document, Record, RecordPage
from app.imaging.preprocess import InvalidImageError
from app.modules.base import OcrModule, ProcessingContext
from app.modules.registry import all_modules, get_module
from app.ocr.factory import get_ocr_engine
from app.ocr.languages import AUTO, LANGUAGES
from app.parsers.registry import get_parser
from app.security.crypto import EncryptionKeyError, FileCipher
from app.services.audit import record as audit
from app.services.exports import to_markdown, to_searchable_pdf, to_txt
from app.services.queries import MAX_PAGE_SIZE, end_of, start_of
from app.services.records import CardPolicy, create_record, delete_record, update_record
from app.services.settings import get_card_storage, get_default_language, get_languages
from app.storage.encrypted_store import EncryptedFileStore
from app.web.deps import get_session, get_store

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[EncryptedFileStore, Depends(get_store)]
EXPORT_TYPES = {"pdf": "application/pdf", "txt": "text/plain; charset=utf-8", "md": "text/markdown; charset=utf-8"}
PROCESSING_FAILED = "Não foi possível processar as imagens. Tente novamente ou envie outras fotos."


class ModuleOut(BaseModel):
    key: str
    name: str
    description: str
    icon: str
    multi_page: bool
    max_pages: int
    page_labels: list[str]
    exports: list[str]
    kinds: dict[str, str]


class LanguageOut(BaseModel):
    code: str
    name: str
    pack: str


class RecordSummary(BaseModel):
    id: int
    module: str
    kind: str | None
    title: str | None
    status: str
    language: str | None
    confidence: float | None
    page_count: int
    created_at: datetime
    thumbnail_url: str | None


class RecordField(BaseModel):
    name: str
    label: str
    kind: str
    value: str
    confidence: float | None
    issues: list[str]


class RecordPageOut(BaseModel):
    id: int
    number: int
    thumbnail_url: str | None
    full_url: str | None
    text: str
    columns: int | None


class CardOut(BaseModel):
    brand: str | None
    last4: str | None
    holder_name: str | None
    expiry: str | None
    luhn_valid: bool
    number_stored: bool


class RecordDetail(RecordSummary):
    module_name: str
    kind_label: str | None
    fields: list[RecordField]
    issues: list[dict[str, str]]
    pages: list[RecordPageOut]
    exports: list[str]
    card: CardOut | None


class RecordReviewIn(BaseModel):
    values: dict[str, str]


class SearchHit(BaseModel):
    module: str
    id: int
    title: str
    subtitle: str
    status: str
    created_at: datetime
    url: str


class SearchOut(BaseModel):
    items: list[SearchHit]
    total: int


def module_out(module: OcrModule) -> ModuleOut:
    return ModuleOut(
        key=module.key,
        name=module.name,
        description=module.description,
        icon=module.icon,
        multi_page=module.multi_page,
        max_pages=module.max_pages,
        page_labels=list(module.page_labels),
        exports=list(module.exports),
        kinds=dict(module.kinds),
    )


def page_urls(page: RecordPage) -> tuple[str | None, str | None]:
    base = f"/api/record-pages/{page.id}"
    thumbnail = f"{base}/thumbnail" if page.thumbnail_path else None
    full = f"{base}/processed" if page.processed_path else None
    return thumbnail, full


def record_summary(record: Record) -> RecordSummary:
    first = record.pages[0] if record.pages else None
    return RecordSummary(
        id=record.id,
        module=record.module,
        kind=record.kind,
        title=record.title,
        status=record.status,
        language=record.language,
        confidence=record.confidence,
        page_count=record.page_count,
        created_at=record.created_at,
        thumbnail_url=page_urls(first)[0] if first else None,
    )


def record_detail(record: Record) -> RecordDetail:
    module = get_module(record.module)
    values = record.data.get("fields", {})
    issues_by_field: dict[str, list[str]] = {}
    for issue in record.issues or []:
        issues_by_field.setdefault(issue.get("field", ""), []).append(issue.get("message", ""))
    fields = [
        RecordField(
            name=spec.name,
            label=spec.label,
            kind=spec.kind,
            value=values.get(spec.name, ""),
            confidence=(record.field_confidence or {}).get(spec.name),
            issues=issues_by_field.get(spec.name, []),
        )
        for spec in module.fields_for(record.kind)
    ]
    pages = []
    for page in record.pages:
        thumbnail, full = page_urls(page)
        pages.append(
            RecordPageOut(
                id=page.id,
                number=page.page_number,
                thumbnail_url=thumbnail,
                full_url=full,
                text=page.text or "",
                columns=(page.layout or {}).get("columns"),
            )
        )
    card = None
    if record.card:
        card = CardOut(
            brand=record.card.brand,
            last4=record.card.last4,
            holder_name=record.card.holder_name,
            expiry=record.card.expiry,
            luhn_valid=record.card.luhn_valid,
            number_stored=record.card.encrypted_number is not None,
        )
    return RecordDetail(
        **record_summary(record).model_dump(),
        module_name=module.name,
        kind_label=module.kinds.get(record.kind or ""),
        fields=fields,
        issues=record.issues or [],
        pages=pages,
        exports=list(module.exports),
        card=card,
    )


def current_user_id(request: Request) -> int | None:
    return request.session.get("user_id")


def load_record(session: Session, record_id: int) -> Record:
    record = session.get(Record, record_id)
    if record is None:
        raise HTTPException(404, "Registro não encontrado")
    return record


def card_policy(request: Request, session: Session) -> CardPolicy:
    key = request.app.state.settings.card_encryption_key
    if not key or not get_card_storage(session):
        return CardPolicy(False, None)
    try:
        return CardPolicy(True, FileCipher(key))
    except EncryptionKeyError:
        return CardPolicy(False, None)


@router.get("/modules")
def modules() -> list[ModuleOut]:
    return [module_out(module) for module in all_modules()]


@router.get("/languages")
def languages() -> list[LanguageOut]:
    return [LanguageOut(code=language.code, name=language.name, pack=language.pack) for language in LANGUAGES.values()]


@router.get("/records")
def list_records(
    session: SessionDep,
    module: str = "",
    kind: str = "",
    q: str = "",
    status: str = "",
    created_from: Annotated[date | None, Query(alias="from")] = None,
    created_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
):
    conditions = []
    if module:
        conditions.append(Record.module == module)
    if kind:
        conditions.append(Record.kind == kind)
    if status:
        conditions.append(Record.status == status)
    if q.strip():
        term = f"%{q.strip()}%"
        conditions.append(or_(Record.title.ilike(term), Record.search_text.ilike(term)))
    if created_from:
        conditions.append(Record.created_at >= start_of(created_from))
    if created_to:
        conditions.append(Record.created_at < end_of(created_to))
    statement = select(Record).options(selectinload(Record.pages))
    if conditions:
        statement = statement.where(and_(*conditions))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = session.scalars(
        statement.order_by(Record.created_at.desc(), Record.id.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return {"items": [record_summary(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("/records", status_code=201)
async def upload_record(
    request: Request,
    session: SessionDep,
    store: StoreDep,
    module: Annotated[str, Form()],
    pages: Annotated[list[UploadFile], File()],
    language: Annotated[str, Form()] = "",
    options: Annotated[str, Form()] = "{}",
) -> RecordDetail:
    try:
        selected = get_module(module)
    except KeyError as error:
        raise HTTPException(400, str(error)) from error
    files = [page for page in pages if page.filename]
    if not files:
        raise HTTPException(400, "Envie pelo menos uma imagem.")
    if len(files) > selected.max_pages:
        raise HTTPException(400, f"Este módulo aceita até {selected.max_pages} imagem(ns).")
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    uploads = []
    for upload in files:
        content = await upload.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(413, "Imagem maior que o limite permitido")
        uploads.append(content)
    try:
        parsed_options = json.loads(options or "{}")
    except json.JSONDecodeError as error:
        raise HTTPException(400, "Opções inválidas") from error
    settings = request.app.state.settings
    override = getattr(request.app.state, "engine_for_pack", None)
    context = ProcessingContext(
        engine_for_pack=override or (lambda pack: get_ocr_engine(settings.ocr_engine, settings.ocr_device, pack)),
        enabled_languages=get_languages(session),
        language=language or get_default_language(session) or AUTO,
        options=parsed_options if isinstance(parsed_options, dict) else {},
    )
    try:
        record = await run_in_threadpool(
            create_record, session, store, selected, context, uploads, current_user_id(request), card_policy(request, session)
        )
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        logger.exception("Falha ao processar registro do módulo %s", module)
        session.rollback()
        raise HTTPException(500, PROCESSING_FAILED) from error
    return record_detail(record)


@router.get("/records/{record_id}")
def show_record(request: Request, record_id: int, session: SessionDep) -> RecordDetail:
    record = load_record(session, record_id)
    audit(session, current_user_id(request), "view", f"record:{record.module}", record.id)
    session.commit()
    return record_detail(record)


@router.put("/records/{record_id}")
def review_record(request: Request, record_id: int, payload: RecordReviewIn, session: SessionDep) -> RecordDetail:
    record = load_record(session, record_id)
    update_record(session, record, get_module(record.module), payload.values, current_user_id(request))
    return record_detail(record)


@router.delete("/records/{record_id}", status_code=204)
def remove_record(request: Request, record_id: int, session: SessionDep, store: StoreDep) -> Response:
    delete_record(session, store, load_record(session, record_id), current_user_id(request))
    return Response(status_code=204)


@router.get("/records/{record_id}/export/{export_type}")
def export_record(request: Request, record_id: int, export_type: str, session: SessionDep, store: StoreDep) -> Response:
    record = load_record(session, record_id)
    if export_type not in get_module(record.module).exports or export_type not in EXPORT_TYPES:
        raise HTTPException(404, "Exportação indisponível para este módulo")
    content = {"txt": lambda: to_txt(record), "md": lambda: to_markdown(record), "pdf": lambda: to_searchable_pdf(record, store)}[
        export_type
    ]()
    audit(session, current_user_id(request), "export", f"record:{record.module}", record.id, export_type)
    session.commit()
    filename = f"lince-{record.module}-{record.id}.{export_type}"
    return Response(
        content, media_type=EXPORT_TYPES[export_type], headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/record-pages/{page_id}/{variant}")
def record_page_image(request: Request, page_id: int, variant: str, session: SessionDep, store: StoreDep) -> Response:
    page = session.get(RecordPage, page_id)
    if page is None:
        raise HTTPException(404, "Página não encontrada")
    paths = {
        "thumbnail": (page.thumbnail_path, "image/webp"),
        "processed": (page.processed_path, "image/jpeg"),
        "original": (page.original_path, page.original_mime),
    }
    path, media_type = paths.get(variant, (None, None))
    if not path:
        raise HTTPException(404, "Imagem não disponível")
    if variant != "thumbnail":
        audit(session, current_user_id(request), "view", "image", page.id, f"{variant} do registro #{page.record_id}")
        session.commit()
    return Response(store.load(path), media_type=media_type, headers={"Cache-Control": "private, max-age=300"})


@router.get("/search")
def search(
    session: SessionDep,
    q: str = "",
    module: str = "",
    status: str = "",
    created_from: Annotated[date | None, Query(alias="from")] = None,
    created_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 30,
) -> SearchOut:
    term = q.strip()
    limit = page * page_size
    hits: list[SearchHit] = []
    total = 0
    if module in ("", "identity"):
        conditions = []
        if term:
            conditions.append(
                or_(
                    Document.full_name.ilike(f"%{term}%"),
                    Document.cpf.like(f"%{''.join(filter(str.isdigit, term)) or term}%"),
                    Document.raw_text.ilike(f"%{term}%"),
                )
            )
        if status:
            conditions.append(Document.status == status)
        if created_from:
            conditions.append(Document.processed_at >= start_of(created_from))
        if created_to:
            conditions.append(Document.processed_at < end_of(created_to))
        statement = select(Document).where(and_(*conditions)) if conditions else select(Document)
        total += session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        for document in session.scalars(statement.order_by(Document.processed_at.desc()).limit(limit)):
            hits.append(
                SearchHit(
                    module="identity",
                    id=document.id,
                    title=document.full_name or "Titular não identificado",
                    subtitle=get_parser(document.doc_type).display_name,
                    status=document.status,
                    created_at=document.processed_at,
                    url=f"/documentos/{document.id}",
                )
            )
    if module != "identity":
        conditions = []
        if module:
            conditions.append(Record.module == module)
        if term:
            conditions.append(or_(Record.title.ilike(f"%{term}%"), Record.search_text.ilike(f"%{term}%")))
        if status:
            conditions.append(Record.status == status)
        if created_from:
            conditions.append(Record.created_at >= start_of(created_from))
        if created_to:
            conditions.append(Record.created_at < end_of(created_to))
        statement = select(Record).where(and_(*conditions)) if conditions else select(Record)
        total += session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        for record in session.scalars(statement.order_by(Record.created_at.desc()).limit(limit)):
            hits.append(
                SearchHit(
                    module=record.module,
                    id=record.id,
                    title=record.title or "Sem título",
                    subtitle=get_module(record.module).name,
                    status=record.status,
                    created_at=record.created_at,
                    url=f"/registros/{record.id}",
                )
            )
    hits.sort(key=lambda hit: hit.created_at.replace(tzinfo=None), reverse=True)
    return SearchOut(items=hits[(page - 1) * page_size : limit], total=total)
