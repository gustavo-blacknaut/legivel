import json
import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from legivel.auth.permissions import Permission
from legivel.db.models import Record, RecordPage
from legivel.imaging.preprocess import InvalidImageError
from legivel.modules.base import OcrModule, ProcessingContext
from legivel.modules.registry import all_modules, get_module
from legivel.ocr.languages import AUTO, LANGUAGES
from legivel.parsers.registry import get_parser
from legivel.services.audit import record as audit
from legivel.services.exports import to_markdown, to_searchable_pdf, to_txt
from legivel.services.queries import MAX_PAGE_SIZE, ListFilters, end_of, list_documents, start_of
from legivel.services.records import CardPolicy, create_record, delete_record, update_record
from legivel.services.settings import RuntimeSettings
from legivel.storage.file_store import FileStore
from legivel.web.deps import RuntimeDep, SessionDep, get_store, pack_engines, permitted
from legivel.web.schemas import PageOut

router = APIRouter(prefix="/api", tags=["records"])
logger = logging.getLogger(__name__)
StoreDep = Annotated[FileStore, Depends(get_store)]
Viewer = permitted(Permission.DOCUMENTS_VIEW)
Uploader = permitted(Permission.DOCUMENTS_UPLOAD)
Reviewer = permitted(Permission.DOCUMENTS_REVIEW)
Remover = permitted(Permission.DOCUMENTS_DELETE)
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
            number_stored=record.card.full_number is not None,
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


def load_record(session: Session, record_id: int) -> Record:
    record = session.get(Record, record_id)
    if record is None:
        raise HTTPException(404, "Registro não encontrado")
    return record


def card_policy(request: Request, runtime: RuntimeSettings) -> CardPolicy:
    return CardPolicy(bool(runtime.store_card_numbers) and request.app.state.settings.encryption_enabled)


@router.get("/modules")
def modules(user: Viewer) -> list[ModuleOut]:
    return [module_out(module) for module in all_modules()]


@router.get("/languages")
def languages(user: Viewer) -> list[LanguageOut]:
    return [LanguageOut(code=language.code, name=language.name, pack=language.pack) for language in LANGUAGES.values()]


@router.get("/records")
def list_records(
    user: Viewer,
    session: SessionDep,
    runtime: RuntimeDep,
    module: str = "",
    kind: str = "",
    q: str = "",
    status: str = "",
    created_from: Annotated[date | None, Query(alias="from")] = None,
    created_to: Annotated[date | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> PageOut[RecordSummary]:
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
        conditions.append(Record.created_at >= start_of(created_from, runtime.timezone))
    if created_to:
        conditions.append(Record.created_at < end_of(created_to, runtime.timezone))
    statement = select(Record).options(selectinload(Record.pages))
    if conditions:
        statement = statement.where(and_(*conditions))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = session.scalars(
        statement.order_by(Record.created_at.desc(), Record.id.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return PageOut(items=[record_summary(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/records", status_code=201)
async def upload_record(
    request: Request,
    user: Uploader,
    session: SessionDep,
    store: StoreDep,
    runtime: RuntimeDep,
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
    max_bytes = runtime.upload_max_mb * 1024 * 1024
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
    enabled = runtime.reading_language_list
    if language and language != AUTO and language not in enabled:
        raise HTTPException(400, "Idioma de leitura não habilitado nas configurações.")
    context = ProcessingContext(
        engine_for_pack=pack_engines(request, runtime.ocr_device),
        enabled_languages=enabled,
        language=language or runtime.default_reading_language,
        options=parsed_options if isinstance(parsed_options, dict) else {},
    )
    try:
        record = await run_in_threadpool(
            create_record, session, store, selected, context, uploads, user.id, card_policy(request, runtime)
        )
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        logger.error("Falha ao processar registro do módulo %s: %s", module, type(error).__name__)
        session.rollback()
        raise HTTPException(500, PROCESSING_FAILED) from error
    return record_detail(record)


@router.get("/records/{record_id}")
def show_record(record_id: int, user: Viewer, session: SessionDep) -> RecordDetail:
    record = load_record(session, record_id)
    audit(session, user.id, "view", f"record:{record.module}", record.id)
    session.commit()
    return record_detail(record)


@router.put("/records/{record_id}")
def review_record(record_id: int, payload: RecordReviewIn, user: Reviewer, session: SessionDep) -> RecordDetail:
    record = load_record(session, record_id)
    update_record(session, record, get_module(record.module), payload.values, user.id)
    return record_detail(record)


@router.delete("/records/{record_id}", status_code=204)
def remove_record(record_id: int, user: Remover, session: SessionDep, store: StoreDep) -> Response:
    delete_record(session, store, load_record(session, record_id), user.id)
    return Response(status_code=204)


@router.get("/records/{record_id}/export/{export_type}")
def export_record(record_id: int, export_type: str, user: Viewer, session: SessionDep, store: StoreDep) -> Response:
    record = load_record(session, record_id)
    if export_type not in get_module(record.module).exports or export_type not in EXPORT_TYPES:
        raise HTTPException(404, "Exportação indisponível para este módulo")
    content = {"txt": lambda: to_txt(record), "md": lambda: to_markdown(record), "pdf": lambda: to_searchable_pdf(record, store)}[
        export_type
    ]()
    audit(session, user.id, "export", f"record:{record.module}", record.id, export_type)
    session.commit()
    filename = f"legivel-{record.module}-{record.id}.{export_type}"
    return Response(
        content, media_type=EXPORT_TYPES[export_type], headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/record-pages/{page_id}/{variant}")
def record_page_image(
    page_id: int, variant: str, user: Viewer, session: SessionDep, store: StoreDep, runtime: RuntimeDep
) -> Response:
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
    if variant == "original" and Permission.IMAGES_ORIGINAL not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Você não tem permissão para esta ação.")
    if variant != "thumbnail":
        audit(session, user.id, "view", "image", page.id, f"{variant} do registro #{page.record_id}")
        session.commit()
    return Response(store.load(path), media_type=media_type, headers={"Cache-Control": "private, max-age=300"})


@router.get("/search")
def search(
    user: Viewer,
    session: SessionDep,
    runtime: RuntimeDep,
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
        filters = ListFilters(term, "", status, created_from, created_to, page=1, page_size=min(limit, MAX_PAGE_SIZE))
        documents = list_documents(session, filters, runtime.timezone)
        total += documents.total
        hits.extend(
            SearchHit(
                module="identity",
                id=document.id,
                title=document.full_name or "Titular não identificado",
                subtitle=get_parser(document.doc_type).display_name,
                status=document.status,
                created_at=document.processed_at,
                url=f"/documentos/{document.id}",
            )
            for document in documents.items
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
            conditions.append(Record.created_at >= start_of(created_from, runtime.timezone))
        if created_to:
            conditions.append(Record.created_at < end_of(created_to, runtime.timezone))
        statement = select(Record).where(and_(*conditions)) if conditions else select(Record)
        total += session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        hits.extend(
            SearchHit(
                module=record.module,
                id=record.id,
                title=record.title or "Sem título",
                subtitle=get_module(record.module).name,
                status=record.status,
                created_at=record.created_at,
                url=f"/registros/{record.id}",
            )
            for record in session.scalars(statement.order_by(Record.created_at.desc()).limit(limit))
        )
    hits.sort(key=lambda hit: hit.created_at.replace(tzinfo=None), reverse=True)
    return SearchOut(items=hits[(page - 1) * page_size : limit], total=total)
