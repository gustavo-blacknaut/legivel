import json
import shutil
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from legivel.auth.permissions import Permission
from legivel.db.base import utc_now
from legivel.db.models import Document, DocumentImage, ProcessingJob, Record, RecordPage, ReviewRevision, User
from legivel.modules.registry import get_module
from legivel.services import backups
from legivel.services.audit import record as audit
from legivel.services.batch_export import export_batch
from legivel.services.documents import document_values, review_document
from legivel.services.pdf_import import inspect_pdf, render_pdf
from legivel.services.records import update_record
from legivel.services.settings import LOGO_PATH_KEY, stored_values
from legivel.storage.file_store import ALLOWED_CATEGORIES
from legivel.web.deps import RuntimeDep, SessionDep, permitted
from legivel.web.routes import StoreDep

router = APIRouter(prefix="/api", tags=["maintenance"])
Admin = permitted(Permission.SETTINGS_MANAGE)
Revealer = permitted(Permission.DATA_REVEAL)
Uploader = permitted(Permission.DOCUMENTS_UPLOAD)
Reviewer = permitted(Permission.DOCUMENTS_REVIEW)


def load_entity(session, entity, entity_id):
    item = session.get(Document if entity == "document" else Record, entity_id)
    if not item:
        raise HTTPException(404, "Documento não encontrado.")
    return item


@router.get("/history/{entity}/{entity_id}")
def history(entity: Literal["document", "record"], entity_id: int, user: Revealer, session: SessionDep):
    load_entity(session, entity, entity_id)
    column = ReviewRevision.document_id if entity == "document" else ReviewRevision.record_id
    revisions = session.scalars(select(ReviewRevision).where(column == entity_id).order_by(ReviewRevision.id.desc()).limit(100))
    result = []
    for revision in revisions:
        author = session.get(User, revision.user_id) if revision.user_id else None
        result.append(
            {
                "id": revision.id,
                "author": author.name if author else "Conta removida",
                "created_at": revision.created_at,
                "changes": {
                    name: {"before": revision.before.get(name, ""), "after": revision.after.get(name, "")}
                    for name in revision.before.keys() | revision.after.keys()
                    if revision.before.get(name, "") != revision.after.get(name, "")
                },
            }
        )
    return result


@router.post("/history/{entity}/{entity_id}/{revision_id}/undo")
def undo(
    entity: Literal["document", "record"],
    entity_id: int,
    revision_id: int,
    user: Reviewer,
    runtime: RuntimeDep,
    session: SessionDep,
):
    if Permission.DATA_REVEAL not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Desfazer exige permissão para revelar os dados.")
    model = Document if entity == "document" else Record
    item = session.scalar(select(model).where(model.id == entity_id).with_for_update())
    if not item:
        raise HTTPException(404, "Documento não encontrado.")
    column = ReviewRevision.document_id if entity == "document" else ReviewRevision.record_id
    latest = session.scalar(select(ReviewRevision).where(column == entity_id).order_by(ReviewRevision.id.desc()).limit(1))
    current = document_values(item) if entity == "document" else item.data.get("fields", {})
    if not latest or latest.id != revision_id or current != latest.after:
        raise HTTPException(409, "Os dados mudaram. Atualize o histórico antes de desfazer.")
    audit(session, user.id, "undo", entity, entity_id, str(revision_id))
    if entity == "document":
        review_document(session, item, latest.before, user.id)
    else:
        update_record(session, item, get_module(item.module), latest.before, user.id)
    return {"detail": "Revisão desfeita. A alteração foi registrada no histórico."}


async def read_limited(upload, limit=100 * 1024 * 1024):
    content = await upload.read(limit + 1)
    if not content or len(content) > limit:
        raise HTTPException(413, "Arquivo vazio ou acima do limite permitido.")
    return content


@router.post("/pdf/inspect")
async def pdf_info(user: Uploader, file: Annotated[UploadFile, File()], password: Annotated[str, Form()] = ""):
    try:
        return await run_in_threadpool(inspect_pdf, await read_limited(file), password)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/pdf/render")
async def pdf_pages(
    user: Uploader,
    file: Annotated[UploadFile, File()],
    selections: Annotated[str, Form()],
    password: Annotated[str, Form()] = "",
    preview: Annotated[bool, Form()] = False,
):
    try:
        choices = json.loads(selections)
        if not isinstance(choices, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("page"), int) for item in choices
        ):
            raise ValueError("Seleção de páginas inválida.")
        pages = await run_in_threadpool(render_pdf, await read_limited(file), choices, password, preview)
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(400, "PDF ou seleção inválidos: " + str(error)) from error
    import base64

    return {
        "pages": [
            {"page": choice["page"], "image": base64.b64encode(content).decode()}
            for choice, content in zip(choices, pages, strict=True)
        ]
    }


class BatchIn(BaseModel):
    entity: Literal["document", "record"]
    ids: list[int] = Field(min_length=1, max_length=100)
    format: Literal["csv", "xlsx", "zip"]


@router.post("/export/batch")
def batch(payload: BatchIn, user: Revealer, runtime: RuntimeDep, session: SessionDep, store: StoreDep):
    if payload.format == "zip" and Permission.IMAGES_ORIGINAL not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Exportar imagens exige acesso aos originais.")
    ids = list(dict.fromkeys(payload.ids))
    items = [load_entity(session, payload.entity, item_id) for item_id in ids]
    # The standard card fields contain only masked PAN; never export CardDetail.full_number.
    try:
        content = export_batch(items, payload.entity, payload.format, store)
    except (OSError, ValueError) as error:
        raise HTTPException(409, "Há arquivos ausentes. Confira o armazenamento.") from error
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(413, "Exportação acima de 200 MB. Selecione menos documentos.")
    audit(session, user.id, "export", "batch", details=f"{len(items)} {payload.entity}: {payload.format}")
    session.commit()
    types = {
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "zip": "application/zip",
    }
    return Response(
        content,
        media_type=types[payload.format],
        headers={"Content-Disposition": f'attachment; filename="legivel-lote.{payload.format}"'},
    )


def referenced_files(session) -> set[str]:
    paths = {
        path
        for model in (DocumentImage, RecordPage)
        for item in session.scalars(select(model))
        for path in (item.original_path, item.processed_path, item.thumbnail_path)
        if path
    }
    paths.update(path for job in session.scalars(select(ProcessingJob)) for path in job.payload.get("paths", []))
    logo = stored_values(session).get(LOGO_PATH_KEY)
    if logo:
        paths.add(logo)
    return paths


def disk_files(settings):
    root = settings.storage_dir.resolve()
    for category in ALLOWED_CATEGORIES:
        for path in (root / category).rglob("*.bin"):
            if not path.is_symlink() and path.resolve().is_relative_to(root):
                yield path, path.relative_to(root).as_posix()


@router.get("/maintenance")
def maintenance(request: Request, user: Admin, session: SessionDep):
    settings = request.app.state.settings
    references = referenced_files(session)
    files = {relative: path for path, relative in disk_files(settings)}
    root = settings.storage_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    counts = {
        status: count
        for status, count in session.execute(select(ProcessingJob.status, func.count()).group_by(ProcessingJob.status))
    }
    return {
        "storage_bytes": sum(path.stat().st_size for path in files.values()),
        "free_bytes": usage.free,
        "missing_files": len(references - files.keys()),
        "unreferenced_files": len(files.keys() - references),
        "queue": counts,
        "backup": backups.backup_status(settings),
        "restore_pending": (backups.maintenance_dir(settings) / "restore.pending").exists(),
        "database": "PostgreSQL" if settings.database_url.startswith("postgres") else "SQLite",
        "ocr": settings.ocr_engine,
        "queue_enabled": settings.background_jobs,
    }


@router.post("/maintenance/cleanup")
def cleanup(request: Request, user: Admin, session: SessionDep):
    references = referenced_files(session)
    cutoff = (utc_now() - timedelta(hours=24)).timestamp()
    removed = 0
    for path, relative in disk_files(request.app.state.settings):
        if relative not in references and path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    audit(session, user.id, "cleanup", "storage", details=f"{removed} arquivos sem referência")
    session.commit()
    return {"removed": removed}


@router.post("/maintenance/backups")
def backup(request: Request, user: Admin, session: SessionDep, password: Annotated[str, Form()]):
    try:
        content = backups.create_backup(request.app.state.settings, password)
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error)) from error
    audit(session, user.id, "backup", "system")
    session.commit()
    return Response(
        content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="legivel-backup.lgb"'},
    )


@router.post("/maintenance/backups/verify")
async def verify(
    request: Request, user: Admin, session: SessionDep, file: Annotated[UploadFile, File()], password: Annotated[str, Form()]
):
    try:
        manifest, files = await run_in_threadpool(
            backups.verify_backup, request.app.state.settings, await read_limited(file, backups.MAX_ARCHIVE), password
        )
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error)) from error
    status = backups.backup_status(request.app.state.settings)
    status["verified_at"] = utc_now().isoformat()
    backups.write_status(request.app.state.settings, status)
    audit(session, user.id, "backup_verify", "system")
    session.commit()
    return {
        "created_at": manifest["created_at"],
        "files": len(files),
        "rows": sum(len(rows) for rows in manifest["tables"].values()),
        "detail": "Recuperação testada em banco isolado.",
    }


@router.post("/maintenance/backups/restore")
async def restore(
    request: Request,
    user: Admin,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    password: Annotated[str, Form()],
    confirmation: Annotated[str, Form()],
):
    if confirmation != "RESTAURAR":
        raise HTTPException(400, "Digite RESTAURAR para substituir os dados no próximo reinício.")
    with request.app.state.maintenance_lock:
        if getattr(request.app.state, "restore_pending", False):
            raise HTTPException(409, "Já existe uma restauração em preparação. Aguarde ou cancele a restauração pendente.")
        request.app.state.restore_pending = True
        if session.scalar(
            select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status.in_(("running", "cancel_requested")))
        ):
            request.app.state.restore_pending = False
            raise HTTPException(409, "Aguarde as tarefas em execução antes de preparar a restauração.")
        request.app.state.restore_preparing = True
    try:
        manifest, files = await run_in_threadpool(
            backups.verify_backup, request.app.state.settings, await read_limited(file, backups.MAX_ARCHIVE), password
        )
        await run_in_threadpool(backups.stage_restore, request.app.state.settings, manifest, files)
    except (ValueError, OSError) as error:
        raise HTTPException(400, str(error)) from error
    finally:
        request.app.state.restore_pending = (backups.maintenance_dir(request.app.state.settings) / "restore.pending").exists()
        request.app.state.restore_preparing = False
    audit(session, user.id, "restore_prepare", "system")
    session.commit()
    return {"detail": "Restauração preparada. Reinicie a API para aplicar. As gravações estão pausadas."}


@router.delete("/maintenance/backups/restore", status_code=204)
def cancel_restore(request: Request, user: Admin):
    if getattr(request.app.state, "restore_preparing", False):
        raise HTTPException(409, "Aguarde a conferência do backup antes de cancelar.")
    (backups.maintenance_dir(request.app.state.settings) / "restore.pending").unlink(missing_ok=True)
    request.app.state.restore_pending = False
