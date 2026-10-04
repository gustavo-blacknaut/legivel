import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentImage, DocumentStatus, ImageSide, Person, ScanLink
from app.imaging.preprocess import InvalidImageError
from app.ocr.base import OcrEngine
from app.parsers.registry import available_parsers, get_parser
from app.services.audit import record
from app.services.documents import (
    UploadedSide,
    delete_document,
    delete_person,
    process_document,
    reprocess_document,
    review_document,
)
from app.services.people import PersonUpdateError, update_person, verify_person
from app.services.queries import MAX_PAGE_SIZE, ListFilters, list_audit, list_documents, list_people
from app.services.scan_links import LinkState, create_link, find_by_token, link_state, list_links, revoke_link, submit_to_link
from app.services.settings import get_timezone, set_timezone, valid_timezones
from app.storage.encrypted_store import EncryptedFileStore
from app.web.deps import get_engine, get_session, get_store
from app.web.schemas import (
    AuditOut,
    DocumentDetail,
    DocumentSummary,
    DocumentTypeOut,
    OverviewOut,
    PageOut,
    PersonDetail,
    PersonOut,
    PersonUpdateIn,
    PublicLinkOut,
    ReprocessIn,
    ReviewIn,
    ScanLinkCreated,
    ScanLinkIn,
    ScanLinkOut,
    SettingsIn,
    SettingsOut,
    StatsOut,
    SystemOut,
    VerificationOut,
    document_detail,
    document_summary,
    person_detail,
    person_out,
)

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[EncryptedFileStore, Depends(get_store)]
EngineDep = Annotated[OcrEngine, Depends(get_engine)]
RECENT_LIMIT = 200
NO_IMAGE_MESSAGE = "Envie pelo menos uma foto do documento."
PROCESSING_FAILED_MESSAGE = "Não foi possível processar a imagem. Tente novamente ou envie outra foto."


def current_user_id(request: Request) -> int | None:
    return request.session.get("user_id")


def load_document(session: Session, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Documento não encontrado")
    return document


async def read_sides(request: Request, front: UploadFile | None, back: UploadFile | None) -> list[UploadedSide]:
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    sides = []
    for side, upload in ((ImageSide.FRONT, front), (ImageSide.BACK, back)):
        if upload is None or not upload.filename:
            continue
        content = await upload.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(413, "Imagem maior que o limite permitido")
        sides.append(UploadedSide(side, content))
    if not sides:
        raise HTTPException(400, NO_IMAGE_MESSAGE)
    return sides


def detail(document: Document) -> DocumentDetail:
    return document_detail(document, get_parser(document.doc_type))


@router.get("/document-types")
def document_types() -> list[DocumentTypeOut]:
    return [DocumentTypeOut(doc_type=parser.doc_type, display_name=parser.display_name) for parser in available_parsers()]


@router.get("/overview")
def overview(session: SessionDep) -> OverviewOut:
    documents = session.scalars(select(Document).order_by(Document.processed_at.desc()).limit(RECENT_LIMIT)).all()
    stats = StatsOut(
        documents=session.scalar(select(func.count(Document.id))),
        pending=session.scalar(select(func.count(Document.id)).where(Document.status == DocumentStatus.PENDING_REVIEW)),
        people=session.scalar(select(func.count(Person.id))),
    )
    return OverviewOut(
        stats=stats,
        documents=[document_summary(document, get_parser(document.doc_type)) for document in documents],
    )


@router.post("/documents", status_code=201)
async def upload_document(
    request: Request,
    session: SessionDep,
    store: StoreDep,
    engine: EngineDep,
    doc_type: Annotated[str, Form()] = "",
    front: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
) -> DocumentDetail:
    sides = await read_sides(request, front, back)
    try:
        requested_type = doc_type or None
        if requested_type:
            get_parser(requested_type)
        document = await run_in_threadpool(
            process_document, session, store, engine, requested_type, sides, current_user_id(request)
        )
    except KeyError as error:
        raise HTTPException(400, str(error)) from error
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        logger.exception("Falha ao processar documento")
        raise HTTPException(500, PROCESSING_FAILED_MESSAGE) from error
    return detail(document)




@router.put("/documents/{document_id}")
def save_document(request: Request, document_id: int, payload: ReviewIn, session: SessionDep) -> DocumentDetail:
    document = load_document(session, document_id)
    allowed = get_parser(document.doc_type).field_names
    values = {name: value for name, value in payload.values.items() if name in allowed}
    review_document(session, document, values, current_user_id(request))
    return detail(document)


@router.post("/documents/{document_id}/reprocess")
async def reprocess(
    request: Request, document_id: int, payload: ReprocessIn, session: SessionDep, store: StoreDep, engine: EngineDep
) -> DocumentDetail:
    document = load_document(session, document_id)
    if payload.doc_type:
        try:
            get_parser(payload.doc_type)
        except KeyError as error:
            raise HTTPException(400, str(error)) from error
    try:
        await run_in_threadpool(
            reprocess_document, session, store, engine, document, current_user_id(request), payload.doc_type or None
        )
    except Exception as error:
        logger.exception("Falha ao reprocessar documento %s", document_id)
        session.rollback()
        raise HTTPException(500, PROCESSING_FAILED_MESSAGE) from error
    return detail(document)


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(request: Request, document_id: int, session: SessionDep, store: StoreDep) -> Response:
    delete_document(session, store, load_document(session, document_id), current_user_id(request))
    return Response(status_code=204)


def list_filters(
    q: str = "",
    doc_type: str = "",
    status: str = "",
    created_from: Annotated[date | None, Query(alias="from")] = None,
    created_to: Annotated[date | None, Query(alias="to")] = None,
    sort: str = "date",
    order: str = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> ListFilters:
    return ListFilters(q, doc_type, status, created_from, created_to, sort, order, page, page_size)


FiltersDep = Annotated[ListFilters, Depends(list_filters)]


@router.get("/people")
def people(session: SessionDep, filters: FiltersDep) -> PageOut[PersonOut]:
    result = list_people(session, filters)
    items = [person_out(person) for person in result.items]
    return PageOut(items=items, total=result.total, page=filters.page, page_size=filters.limit)




@router.get("/documents")
def documents(session: SessionDep, filters: FiltersDep) -> PageOut[DocumentSummary]:
    result = list_documents(session, filters)
    items = [document_summary(document, get_parser(document.doc_type)) for document in result.items]
    return PageOut(items=items, total=result.total, page=filters.page, page_size=filters.limit)


@router.get("/audit")
def audit(session: SessionDep, filters: FiltersDep, action: str = "", entity: str = "") -> PageOut[AuditOut]:
    result = list_audit(session, filters, action, entity)
    items = [AuditOut(**vars(entry)) for entry in result.items]
    return PageOut(items=items, total=result.total, page=filters.page, page_size=filters.limit)


@router.get("/system")
def system(request: Request) -> SystemOut:
    settings = request.app.state.settings
    return SystemOut(
        ocr_engine=settings.ocr_engine,
        ocr_device=settings.ocr_device,
        encrypted_storage=True,
        max_upload_mb=settings.max_upload_mb,
    )


@router.delete("/people/{person_id}", status_code=204)
def remove_person(request: Request, person_id: int, session: SessionDep, store: StoreDep) -> Response:
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "Pessoa não encontrada")
    delete_person(session, store, person, current_user_id(request))
    return Response(status_code=204)


@router.get("/images/{image_id}/{variant}")
def image(request: Request, image_id: int, variant: str, session: SessionDep, store: StoreDep) -> Response:
    stored = session.get(DocumentImage, image_id)
    if stored is None:
        raise HTTPException(404, "Imagem não encontrada")
    variants = {
        "thumbnail": (stored.thumbnail_path, "image/webp"),
        "processed": (stored.processed_path, "image/jpeg"),
        "original": (stored.original_path, stored.original_mime),
    }
    path, media_type = variants.get(variant, (None, None))
    if not path:
        raise HTTPException(404, "Imagem não encontrada")
    if variant in ("original", "processed"):
        record(session, current_user_id(request), "view", "image", stored.id, f"{variant} do documento #{stored.document_id}")
        session.commit()
    return Response(store.load(path), media_type=media_type, headers={"Cache-Control": "private, max-age=300"})


@router.get("/documents/{document_id}")
def show_document(request: Request, document_id: int, session: SessionDep) -> DocumentDetail:
    document = load_document(session, document_id)
    record(session, current_user_id(request), "view", "document", document.id)
    session.commit()
    return detail(document)


def load_person(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "Pessoa não encontrada")
    return person


@router.get("/people/{person_id}")
def show_person(request: Request, person_id: int, session: SessionDep) -> PersonDetail:
    person = load_person(session, person_id)
    record(session, current_user_id(request), "view", "person", person.id)
    session.commit()
    return person_detail(person)


@router.put("/people/{person_id}")
def edit_person(request: Request, person_id: int, payload: PersonUpdateIn, session: SessionDep) -> PersonDetail:
    person = load_person(session, person_id)
    try:
        update_person(session, person, payload.values, current_user_id(request))
    except PersonUpdateError as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error
    return person_detail(person)


@router.post("/people/{person_id}/verify")
def verify(request: Request, person_id: int, session: SessionDep) -> VerificationOut:
    person = load_person(session, person_id)
    result = verify_person(session, person, current_user_id(request))
    return VerificationOut(changes=result.changes, problems=result.problems, person=person_detail(person))


@router.get("/settings")
def read_settings(session: SessionDep) -> SettingsOut:
    return SettingsOut(timezone=get_timezone(session))


@router.put("/settings")
def save_settings(request: Request, payload: SettingsIn, session: SessionDep) -> SettingsOut:
    try:
        set_timezone(session, payload.timezone)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    record(session, current_user_id(request), "update", "settings", None, f"fuso horário: {payload.timezone}")
    session.commit()
    return SettingsOut(timezone=payload.timezone)


@router.get("/settings/timezones")
def timezones() -> list[str]:
    return sorted(valid_timezones())


def scan_link_out(link: ScanLink) -> ScanLinkOut:
    return ScanLinkOut(
        id=link.id,
        label=link.label,
        state=link_state(link),
        created_at=link.created_at,
        expires_at=link.expires_at,
        used_at=link.used_at,
        document_id=link.document_id,
    )


@router.get("/scan-links")
def scan_links(session: SessionDep) -> list[ScanLinkOut]:
    return [scan_link_out(link) for link in list_links(session)]


@router.post("/scan-links", status_code=201)
def new_scan_link(request: Request, payload: ScanLinkIn, session: SessionDep) -> ScanLinkCreated:
    created = create_link(session, current_user_id(request), payload.label, payload.hours)
    return ScanLinkCreated(**scan_link_out(created.link).model_dump(), token=created.token)


@router.delete("/scan-links/{link_id}", status_code=204)
def cancel_scan_link(request: Request, link_id: int, session: SessionDep) -> Response:
    link = session.get(ScanLink, link_id)
    if link is None:
        raise HTTPException(404, "Link não encontrado")
    revoke_link(session, link, current_user_id(request))
    return Response(status_code=204)


public_router = APIRouter(prefix="/api/public")


def active_link(session: Session, token: str) -> ScanLink:
    link = find_by_token(session, token)
    if link is None:
        raise HTTPException(404, "Link inválido.")
    return link


@public_router.get("/scan/{token}")
def public_link(token: str, session: SessionDep) -> PublicLinkOut:
    link = active_link(session, token)
    return PublicLinkOut(label=link.label, state=link_state(link), expires_at=link.expires_at)


@public_router.post("/scan/{token}", status_code=201)
async def public_upload(
    request: Request,
    token: str,
    session: SessionDep,
    store: StoreDep,
    engine: EngineDep,
    front: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
) -> dict[str, str]:
    throttle = request.app.state.login_throttle
    key = f"scan:{request.client.host if request.client else 'unknown'}"
    if throttle.is_blocked(key):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    link = find_by_token(session, token)
    if link is None:
        throttle.record_failure(key)
        raise HTTPException(404, "Link inválido.")
    if link_state(link) != LinkState.ACTIVE:
        raise HTTPException(410, "Este link já foi usado ou expirou.")
    sides = await read_sides(request, front, back)
    try:
        await run_in_threadpool(submit_to_link, session, store, engine, link, sides)
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except PermissionError as error:
        raise HTTPException(410, str(error)) from error
    except Exception as error:
        logger.exception("Falha ao processar envio por link %s", link.id)
        raise HTTPException(500, PROCESSING_FAILED_MESSAGE) from error
    return {"status": "recebido"}
