import hashlib
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from legivel.auth.accounts import has_users
from legivel.auth.permissions import Permission, assignable_permissions
from legivel.db.models import Document, DocumentImage, DocumentStatus, ImageSide, Person, ScanLink, User
from legivel.imaging.preprocess import InvalidImageError, detect_format
from legivel.ocr.base import OcrEngine
from legivel.ocr.status import describe_engine
from legivel.parsers.registry import available_parsers, get_parser
from legivel.security.masking import is_masked
from legivel.services.audit import record
from legivel.services.documents import (
    ImagePolicy,
    UploadedSide,
    delete_document,
    delete_person,
    process_document,
    reprocess_document,
    review_document,
)
from legivel.services.export import export_person
from legivel.services.people import PersonUpdateError, update_person, verify_person
from legivel.services.queries import MAX_PAGE_SIZE, ListFilters, list_audit, list_documents, list_people
from legivel.services.scan_links import LinkState, create_link, find_by_token, link_state, list_links, revoke_link, submit_to_link
from legivel.services.settings import (
    OPTIONS,
    RuntimeSettings,
    SettingError,
    load_runtime,
    set_logo,
    update_role_permissions,
    update_runtime,
    valid_timezones,
)
from legivel.storage.file_store import FileStore
from legivel.web.deps import RuntimeDep, SessionDep, UserDep, engine_for, get_engine, get_store, permitted
from legivel.web.schemas import (
    AuditOut,
    DocumentDetail,
    DocumentSummary,
    DocumentTypeOut,
    InstanceOut,
    OverviewOut,
    PageOut,
    PersonDetail,
    PersonOut,
    PersonUpdateIn,
    PublicLinkOut,
    ReviewIn,
    RolePermissionsIn,
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

router = APIRouter(prefix="/api", tags=["documents"])
public_router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)

StoreDep = Annotated[FileStore, Depends(get_store)]
EngineDep = Annotated[OcrEngine, Depends(get_engine)]
Viewer = permitted(Permission.DOCUMENTS_VIEW)
Uploader = permitted(Permission.DOCUMENTS_UPLOAD)
Reviewer = permitted(Permission.DOCUMENTS_REVIEW)
DocumentRemover = permitted(Permission.DOCUMENTS_DELETE)
OriginalViewer = permitted(Permission.IMAGES_ORIGINAL)
PersonEditor = permitted(Permission.PEOPLE_EDIT)
PersonRemover = permitted(Permission.PEOPLE_DELETE)
LinkManager = permitted(Permission.SCAN_LINKS)
Auditor = permitted(Permission.AUDIT_VIEW)
Administrator = permitted(Permission.SETTINGS_MANAGE)
RECENT_LIMIT = 200
LOGO_MAX_BYTES = 512 * 1024
LOGO_TYPES = {"png": "image/png", "webp": "image/webp", "jpeg": "image/jpeg"}
NO_IMAGE_MESSAGE = "Envie pelo menos uma foto do documento."
PROCESSING_FAILED_MESSAGE = "Não foi possível processar a imagem. Tente novamente ou envie outra foto."
FORMAT_LABELS = {"jpeg": "JPEG", "png": "PNG", "webp": "WebP", "heic": "HEIC"}


def image_policy(request: Request, runtime: RuntimeSettings) -> ImagePolicy:
    return ImagePolicy(
        runtime.image_quality, runtime.compress_originals, request.app.state.settings.original_max_side, runtime.ocr_passes
    )


def load_document(session: Session, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Documento não encontrado")
    return document


async def read_image(runtime: RuntimeSettings, upload: UploadFile) -> bytes:
    max_bytes = runtime.upload_max_mb * 1024 * 1024
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"Imagem maior que o limite de {runtime.upload_max_mb} MB")
    detected = detect_format(content)
    if detected is None:
        raise HTTPException(400, "Arquivo não é uma imagem válida")
    if detected not in runtime.allowed_formats:
        accepted = ", ".join(FORMAT_LABELS[item] for item in runtime.allowed_formats)
        raise HTTPException(415, f"Formato {FORMAT_LABELS[detected]} não aceito. Formatos aceitos: {accepted}.")
    return content


async def read_sides(runtime: RuntimeSettings, front: UploadFile | None, back: UploadFile | None) -> list[UploadedSide]:
    sides = []
    for side, upload in ((ImageSide.FRONT, front), (ImageSide.BACK, back)):
        if upload is None or not upload.filename:
            continue
        sides.append(UploadedSide(side, await read_image(runtime, upload)))
    if not sides:
        raise HTTPException(400, NO_IMAGE_MESSAGE)
    return sides


RevealDep = Annotated[bool, Query(alias="reveal")]


def detail(document: Document, reveal: bool = False) -> DocumentDetail:
    return document_detail(document, get_parser(document.doc_type), reveal)


def allow_reveal(
    session: Session, user: User, runtime: RuntimeSettings, wanted: bool, entity: str, entity_id: int
) -> bool:
    if not wanted:
        return False
    if Permission.DATA_REVEAL not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Você não tem permissão para ver os dados completos.")
    record(session, user.id, "reveal", entity, entity_id)
    session.commit()
    return True


def unmasked(values: dict[str, str | None]) -> dict[str, str | None]:
    return {name: value for name, value in values.items() if not is_masked(value)}


@router.get("/document-types")
def document_types(user: Viewer) -> list[DocumentTypeOut]:
    return [DocumentTypeOut(doc_type=parser.doc_type, display_name=parser.display_name) for parser in available_parsers()]


@router.get("/overview")
def overview(user: Viewer, session: SessionDep) -> OverviewOut:
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
    user: Uploader,
    session: SessionDep,
    store: StoreDep,
    engine: EngineDep,
    runtime: RuntimeDep,
    front: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
) -> DocumentDetail:
    sides = await read_sides(runtime, front, back)
    try:
        document = await run_in_threadpool(
            process_document, session, store, engine, None, sides, user.id, image_policy(request, runtime)
        )
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        logger.exception("Falha ao processar documento")
        raise HTTPException(500, PROCESSING_FAILED_MESSAGE) from error
    return detail(document)


@router.put("/documents/{document_id}")
def save_document(
    document_id: int, payload: ReviewIn, user: Reviewer, session: SessionDep, runtime: RuntimeDep, reveal: RevealDep = False
) -> DocumentDetail:
    document = load_document(session, document_id)
    allowed = get_parser(document.doc_type).field_names
    values = {name: value for name, value in unmasked(payload.values).items() if name in allowed}
    review_document(session, document, values, user.id)
    return detail(document, allow_reveal(session, user, runtime, reveal, "document", document.id))


@router.post("/documents/{document_id}/reprocess")
async def reprocess(
    request: Request,
    document_id: int,
    user: Reviewer,
    session: SessionDep,
    store: StoreDep,
    engine: EngineDep,
    runtime: RuntimeDep,
    reveal: RevealDep = False,
) -> DocumentDetail:
    document = load_document(session, document_id)
    try:
        await run_in_threadpool(reprocess_document, session, store, engine, document, user.id, image_policy(request, runtime))
    except Exception as error:
        logger.exception("Falha ao reprocessar documento %s", document_id)
        session.rollback()
        raise HTTPException(500, PROCESSING_FAILED_MESSAGE) from error
    return detail(document, allow_reveal(session, user, runtime, reveal, "document", document.id))


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(document_id: int, user: DocumentRemover, session: SessionDep, store: StoreDep) -> Response:
    delete_document(session, store, load_document(session, document_id), user.id)
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
def people(user: Viewer, session: SessionDep, filters: FiltersDep, runtime: RuntimeDep) -> PageOut[PersonOut]:
    result = list_people(session, filters, runtime.timezone)
    items = [person_out(person) for person in result.items]
    return PageOut(items=items, total=result.total, page=filters.page, page_size=filters.limit)


@router.get("/documents")
def documents(user: Viewer, session: SessionDep, filters: FiltersDep, runtime: RuntimeDep) -> PageOut[DocumentSummary]:
    result = list_documents(session, filters, runtime.timezone)
    items = [document_summary(document, get_parser(document.doc_type)) for document in result.items]
    return PageOut(items=items, total=result.total, page=filters.page, page_size=filters.limit)


@router.get("/audit")
def audit(
    user: Auditor, session: SessionDep, filters: FiltersDep, runtime: RuntimeDep, action: str = "", entity: str = ""
) -> PageOut[AuditOut]:
    result = list_audit(session, filters, action, entity, runtime.timezone)
    items = [AuditOut(**vars(entry)) for entry in result.items]
    return PageOut(items=items, total=result.total, page=filters.page, page_size=filters.limit)


@router.get("/system")
def system(request: Request, user: Viewer, runtime: RuntimeDep) -> SystemOut:
    settings = request.app.state.settings
    engine = engine_for(request, runtime.ocr_device)
    return SystemOut(
        ocr_engine=settings.ocr_engine,
        ocr_device=runtime.ocr_device,
        ocr_languages=settings.ocr_languages,
        encrypted_storage=request.app.state.store.encrypted,
        database="sqlite" if settings.is_sqlite else "postgresql",
        smtp_configured=settings.smtp_configured,
        upload_max_mb=runtime.upload_max_mb,
        upload_formats=list(runtime.allowed_formats),
        retention_days=runtime.retention_days,
        ocr_status=describe_engine(engine, runtime.ocr_device),
    )


@router.delete("/people/{person_id}", status_code=204)
def remove_person(person_id: int, user: PersonRemover, session: SessionDep, store: StoreDep) -> Response:
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "Pessoa não encontrada")
    delete_person(session, store, person, user.id)
    return Response(status_code=204)


IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic", "image/heif": "heif"}


def image_filename(image: DocumentImage, variant: str, media_type: str) -> str:
    return f"documento-{image.document_id}-{image.side}-{variant}.{IMAGE_EXTENSIONS.get(media_type, 'bin')}"


@router.get("/images/{image_id}/{variant}")
def image(image_id: int, variant: str, user: Viewer, session: SessionDep, store: StoreDep, runtime: RuntimeDep) -> Response:
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
    if variant == "original" and Permission.IMAGES_ORIGINAL not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Você não tem permissão para ver a imagem original.")
    if variant in ("original", "processed"):
        record(session, user.id, "view", "image", stored.id, f"{variant} do documento #{stored.document_id}")
        session.commit()
    headers = {
        "Cache-Control": "private, max-age=300",
        "Content-Disposition": f'inline; filename="{image_filename(stored, variant, media_type)}"',
    }
    return Response(store.load(path), media_type=media_type, headers=headers)


@router.get("/documents/{document_id}")
def show_document(
    document_id: int, user: Viewer, session: SessionDep, runtime: RuntimeDep, reveal: RevealDep = False
) -> DocumentDetail:
    document = load_document(session, document_id)
    record(session, user.id, "view", "document", document.id)
    session.commit()
    return detail(document, allow_reveal(session, user, runtime, reveal, "document", document.id))


def load_person(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(404, "Pessoa não encontrada")
    return person


@router.get("/people/{person_id}")
def show_person(
    person_id: int, user: Viewer, session: SessionDep, runtime: RuntimeDep, reveal: RevealDep = False
) -> PersonDetail:
    person = load_person(session, person_id)
    record(session, user.id, "view", "person", person.id)
    session.commit()
    return person_detail(person, allow_reveal(session, user, runtime, reveal, "person", person.id))


@router.get("/people/{person_id}/export")
def export_person_data(person_id: int, user: Viewer, session: SessionDep, runtime: RuntimeDep) -> JSONResponse:
    if Permission.DATA_REVEAL not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Você não tem permissão para exportar os dados completos.")
    person = load_person(session, person_id)
    content = export_person(session, person)
    record(session, user.id, "export", "person", person.id)
    session.commit()
    return JSONResponse(
        content,
        headers={
            "Content-Disposition": f'attachment; filename="pessoa-{person.id}.json"',
            "Cache-Control": "no-store",
        },
    )


@router.put("/people/{person_id}")
def edit_person(
    person_id: int,
    payload: PersonUpdateIn,
    user: PersonEditor,
    session: SessionDep,
    runtime: RuntimeDep,
    reveal: RevealDep = False,
) -> PersonDetail:
    person = load_person(session, person_id)
    try:
        update_person(session, person, unmasked(payload.values), user.id)
    except PersonUpdateError as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error
    return person_detail(person, allow_reveal(session, user, runtime, reveal, "person", person.id))


@router.post("/people/{person_id}/verify")
def verify(
    person_id: int, user: PersonEditor, session: SessionDep, runtime: RuntimeDep, reveal: RevealDep = False
) -> VerificationOut:
    person = load_person(session, person_id)
    result = verify_person(session, person, user.id)
    revealed = allow_reveal(session, user, runtime, reveal, "person", person.id)
    return VerificationOut(changes=result.changes, problems=result.problems, person=person_detail(person, revealed))


def settings_out(request: Request, runtime: RuntimeSettings) -> SettingsOut:
    settings = request.app.state.settings
    return SettingsOut(
        values=runtime.values,
        defaults={option.key: getattr(settings, option.key) for option in OPTIONS},
        overridden=sorted(runtime.overridden),
        role_permissions=runtime.role_permissions,
        assignable_permissions=assignable_permissions(),
        has_logo=runtime.logo_path is not None,
    )


@router.get("/settings")
def read_settings(request: Request, user: UserDep, runtime: RuntimeDep) -> SettingsOut:
    return settings_out(request, runtime)


@router.put("/settings")
def save_settings(request: Request, payload: SettingsIn, user: Administrator, session: SessionDep) -> SettingsOut:
    if payload.values.get("store_card_numbers") in (True, "true") and not request.app.state.settings.encryption_enabled:
        raise HTTPException(400, "Guardar o número do cartão exige a criptografia ativada.")
    try:
        changed = update_runtime(session, payload.values)
    except SettingError as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error
    if changed:
        record(session, user.id, "update", "settings", None, "; ".join(changed))
    session.commit()
    return settings_out(request, load_runtime(session, request.app.state.settings))


@router.put("/settings/roles")
def save_role_permissions(request: Request, payload: RolePermissionsIn, user: Administrator, session: SessionDep) -> SettingsOut:
    try:
        update_role_permissions(session, payload.role_permissions)
    except SettingError as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error
    summary = "; ".join(f"{role}: {', '.join(values)}" for role, values in payload.role_permissions.items())
    record(session, user.id, "update", "permissions", None, summary)
    session.commit()
    return settings_out(request, load_runtime(session, request.app.state.settings))


@router.put("/settings/logo", status_code=204)
async def upload_logo(
    user: Administrator, session: SessionDep, store: StoreDep, runtime: RuntimeDep, logo: Annotated[UploadFile, File()]
) -> Response:
    content = await logo.read(LOGO_MAX_BYTES + 1)
    if len(content) > LOGO_MAX_BYTES:
        raise HTTPException(413, "O logotipo pode ter no máximo 512 KB")
    detected = detect_format(content)
    if detected not in LOGO_TYPES:
        raise HTTPException(415, "Envie o logotipo em PNG, WebP ou JPEG")
    if runtime.logo_path:
        store.delete(runtime.logo_path)
    stored = store.save("branding", content)
    set_logo(session, stored.relative_path, LOGO_TYPES[detected])
    record(session, user.id, "update", "settings", None, "logotipo atualizado")
    session.commit()
    return Response(status_code=204)


@router.delete("/settings/logo", status_code=204)
def remove_logo(user: Administrator, session: SessionDep, store: StoreDep, runtime: RuntimeDep) -> Response:
    if runtime.logo_path:
        store.delete(runtime.logo_path)
        set_logo(session, None, None)
        record(session, user.id, "update", "settings", None, "logotipo removido")
        session.commit()
    return Response(status_code=204)


@router.get("/settings/timezones")
def timezones(user: UserDep) -> list[str]:
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
def scan_links(user: LinkManager, session: SessionDep) -> list[ScanLinkOut]:
    return [scan_link_out(link) for link in list_links(session)]


@router.post("/scan-links", status_code=201)
def new_scan_link(payload: ScanLinkIn, user: LinkManager, session: SessionDep, runtime: RuntimeDep) -> ScanLinkCreated:
    created = create_link(session, user.id, payload.label, payload.hours or runtime.scan_link_hours)
    return ScanLinkCreated(**scan_link_out(created.link).model_dump(), token=created.token)


@router.delete("/scan-links/{link_id}", status_code=204)
def cancel_scan_link(link_id: int, user: LinkManager, session: SessionDep) -> Response:
    link = session.get(ScanLink, link_id)
    if link is None:
        raise HTTPException(404, "Link não encontrado")
    revoke_link(session, link, user.id)
    return Response(status_code=204)


def logo_version(runtime: RuntimeSettings) -> str | None:
    if not runtime.logo_path:
        return None
    return hashlib.sha256(runtime.logo_path.encode()).hexdigest()[:12]


@public_router.get("/instance")
def instance(request: Request, session: SessionDep, runtime: RuntimeDep) -> InstanceOut:
    version = logo_version(runtime)
    return InstanceOut(
        name=runtime.instance_name,
        default_theme=runtime.default_theme,
        default_language=runtime.default_language,
        timezone=runtime.timezone,
        logo_url=f"/api/public/logo?v={version}" if version else None,
        setup_required=not has_users(session),
        smtp_configured=request.app.state.settings.smtp_configured,
        upload_max_mb=runtime.upload_max_mb,
        upload_formats=list(runtime.allowed_formats),
        password_min_length=runtime.password_min_length,
        password_require_mixed=runtime.password_require_mixed,
        refresh_days=runtime.refresh_days,
    )


@public_router.get("/logo")
def logo(store: StoreDep, runtime: RuntimeDep) -> Response:
    if not runtime.logo_path:
        raise HTTPException(404, "Sem logotipo")
    return Response(
        store.load(runtime.logo_path),
        media_type=runtime.logo_mime or "image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def active_link(request: Request, session: Session, token: str) -> ScanLink:
    throttle = request.app.state.login_throttle
    key = f"scan:{request.client.host if request.client else 'unknown'}"
    if throttle.is_blocked(key):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    link = find_by_token(session, token)
    if link is None:
        throttle.record_failure(key)
        raise HTTPException(404, "Link inválido.")
    return link


@public_router.get("/scan/{token}")
def public_link(request: Request, token: str, session: SessionDep) -> PublicLinkOut:
    link = active_link(request, session, token)
    return PublicLinkOut(label=link.label, state=link_state(link), expires_at=link.expires_at)


@public_router.post("/scan/{token}", status_code=201)
async def public_upload(
    request: Request,
    token: str,
    session: SessionDep,
    store: StoreDep,
    engine: EngineDep,
    runtime: RuntimeDep,
    front: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
) -> dict[str, str]:
    link = active_link(request, session, token)
    if link_state(link) != LinkState.ACTIVE:
        raise HTTPException(410, "Este link já foi usado ou expirou.")
    sides = await read_sides(runtime, front, back)
    try:
        await run_in_threadpool(submit_to_link, session, store, engine, link, sides, image_policy(request, runtime))
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except PermissionError as error:
        raise HTTPException(410, str(error)) from error
    except Exception as error:
        logger.exception("Falha ao processar envio por link %s", link.id)
        raise HTTPException(500, PROCESSING_FAILED_MESSAGE) from error
    return {"status": "recebido"}
