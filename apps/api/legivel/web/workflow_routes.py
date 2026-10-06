from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update

from legivel.auth.permissions import Permission
from legivel.db.models import Document, DocumentImage, OrganizationEntry, ProcessingJob, Record, SavedSearch
from legivel.imaging.quality import assess_photo
from legivel.modules.registry import get_module
from legivel.services.audit import record as audit
from legivel.services.redaction import redacted_image, redacted_pdf
from legivel.web.deps import RuntimeDep, SessionDep, UserDep, permitted
from legivel.web.routes import StoreDep, load_document, read_image, read_sides

router = APIRouter(prefix="/api", tags=["workflow"])
Viewer = permitted(Permission.DOCUMENTS_VIEW)
Uploader = permitted(Permission.DOCUMENTS_UPLOAD)


class JobOut(BaseModel):
    id: int
    module: str
    label: str
    status: str
    completed_pages: int
    total_pages: int
    result_id: int | None
    error: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


@router.post("/capture/check")
async def check_capture(user: Uploader, runtime: RuntimeDep, photo: Annotated[UploadFile, File()]) -> dict:
    return await run_in_threadpool(assess_photo, await read_image(runtime, photo))


def job_for(session, user, job_id):
    job = session.get(ProcessingJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "Tarefa não encontrada")
    return job


@router.get("/jobs")
def jobs(user: UserDep, session: SessionDep) -> list[JobOut]:
    return list(
        session.scalars(
            select(ProcessingJob).where(ProcessingJob.user_id == user.id).order_by(ProcessingJob.id.desc()).limit(200)
        )
    )


@router.post("/jobs", status_code=202)
async def enqueue(
    request: Request,
    user: Uploader,
    runtime: RuntimeDep,
    session: SessionDep,
    store: StoreDep,
    module: Annotated[str, Form()] = "documents",
    front: Annotated[UploadFile | None, File()] = None,
    back: Annotated[UploadFile | None, File()] = None,
    pages: Annotated[list[UploadFile] | None, File()] = None,
    language: Annotated[str, Form()] = "",
    duplicate: Annotated[Literal["ask", "keep", "link", "replace"], Form()] = "ask",
) -> JobOut:
    if not store.encrypted:
        raise HTTPException(400, "A fila exige armazenamento cifrado. Configure a chave de criptografia.")
    sides = []
    if module == "documents":
        uploads = await read_sides(runtime, front, back)
        contents = [item.content for item in uploads]
        sides = [item.side for item in uploads]
        label = (front.filename if front else back.filename) or "Documento"
    else:
        try:
            selected = get_module(module)
        except KeyError as error:
            raise HTTPException(400, "Módulo inválido") from error
        if module == "cards":
            raise HTTPException(400, "Cartões são processados diretamente para não guardar imagens na fila.")
        files = [item for item in pages or [] if item.filename]
        if not files or len(files) > selected.max_pages:
            raise HTTPException(400, f"Envie de 1 a {selected.max_pages} imagens.")
        contents = [await read_image(runtime, item) for item in files]
        label = files[0].filename or "Leitura"
        if language and language != "auto" and language not in runtime.reading_language_list:
            raise HTTPException(400, "Idioma não habilitado")
    existing = None
    if module == "documents":
        import hashlib

        hashes = [hashlib.sha256(content).hexdigest() for content in contents]
        candidates = (
            session.scalars(select(Document).join(Document.images).where(DocumentImage.sha256.in_(hashes))).unique().all()
        )
        for candidate in candidates:
            stored = {image.sha256 for image in candidate.images if image.kind == "page"}
            if stored == set(hashes):
                existing = candidate
                break
        if existing and duplicate == "ask":
            raise HTTPException(409, {"message": "Este documento já foi enviado.", "document_id": existing.id})
    if duplicate == "replace" and Permission.DOCUMENTS_DELETE not in runtime.permissions_of(user.role):
        raise HTTPException(403, "Substituir exige permissão para excluir documentos")
    pending_count = session.scalar(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.user_id == user.id, ProcessingJob.status.in_(("queued", "running", "failed", "cancel_requested"))
        )
    )
    if pending_count >= 500:
        raise HTTPException(429, "A fila está cheia. Aguarde ou cancele tarefas antigas.")
    paths = []
    try:
        if not (existing and duplicate == "link"):
            paths = [store.save("queue", content).relative_path for content in contents]
        job = ProcessingJob(
            user_id=user.id,
            module=module,
            label=label[:200],
            total_pages=len(contents),
            status="completed" if existing and duplicate == "link" else "queued",
            completed_pages=len(contents) if existing and duplicate == "link" else 0,
            result_id=existing.id if existing and duplicate == "link" else None,
            payload={
                "paths": paths,
                "sides": sides,
                "language": language,
                "replace_id": existing.id if existing and duplicate == "replace" else None,
            }
            if paths
            else {},
        )
        session.add(job)
        session.flush()
        audit(session, user.id, "create", "job", job.id)
        session.commit()
    except Exception:
        session.rollback()
        for path in paths:
            store.delete(path)
        raise
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, user: UserDep, session: SessionDep, store: StoreDep) -> JobOut:
    job = job_for(session, user, job_id)
    if job.status in ("queued", "failed"):
        # Conditional transition prevents a worker claim from racing cancellation.
        changed = session.execute(
            update(ProcessingJob).where(ProcessingJob.id == job.id, ProcessingJob.status == job.status).values(status="cancelled")
        )
        session.commit()
        session.refresh(job)
        if changed.rowcount:
            for path in job.payload.get("paths", []):
                store.delete(path)
            job.payload = {}
            session.commit()
    if job.status == "running":
        session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job.id, ProcessingJob.status == "running")
            .values(status="cancel_requested")
        )
        session.commit()
        session.refresh(job)
    return job


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, user: Uploader, session: SessionDep) -> JobOut:
    job = job_for(session, user, job_id)
    if job.status != "failed":
        raise HTTPException(409, "Só tarefas com falha podem ser reenviadas")
    session.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == job.id, ProcessingJob.status == "failed")
        .values(status="queued", error=None, completed_pages=0)
    )
    session.commit()
    session.refresh(job)
    return job


class OrganizationIn(BaseModel):
    folder: str = Field(default="", max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value):
        tags = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 50 for item in tags):
            raise ValueError("Etiquetas devem ter até 50 caracteres")
        return tags


def check_entity(session, entity, entity_id):
    model = {"document": Document, "record": Record}.get(entity)
    if model is None or session.get(model, entity_id) is None:
        raise HTTPException(404, "Item não encontrado")


@router.get("/organization")
def organized(user: Viewer, session: SessionDep, folder: str = "", tag: str = "") -> list[dict]:
    entries = session.scalars(select(OrganizationEntry).where(OrganizationEntry.user_id == user.id)).all()
    result = []
    for entry in entries:
        if (folder and folder != entry.folder) or (tag and tag not in entry.tags):
            continue
        model = Document if entry.entity == "document" else Record
        item = session.get(model, entry.entity_id)
        if item:
            result.append(
                {
                    "id": entry.entity_id,
                    "entity": entry.entity,
                    "folder": entry.folder,
                    "tags": entry.tags,
                    "title": (item.full_name if entry.entity == "document" else item.title) or f"#{item.id}",
                }
            )
    return result


@router.get("/organization/{entity}/{entity_id}")
def organization(entity: str, entity_id: int, user: Viewer, session: SessionDep) -> dict:
    check_entity(session, entity, entity_id)
    entry = session.scalar(
        select(OrganizationEntry).where(
            OrganizationEntry.user_id == user.id, OrganizationEntry.entity == entity, OrganizationEntry.entity_id == entity_id
        )
    )
    return {"folder": entry.folder, "tags": entry.tags} if entry else {"folder": "", "tags": []}


@router.put("/organization/{entity}/{entity_id}")
def save_organization(entity: str, entity_id: int, body: OrganizationIn, user: Viewer, session: SessionDep) -> dict:
    check_entity(session, entity, entity_id)
    entry = session.scalar(
        select(OrganizationEntry).where(
            OrganizationEntry.user_id == user.id, OrganizationEntry.entity == entity, OrganizationEntry.entity_id == entity_id
        )
    )
    if not entry:
        entry = OrganizationEntry(user_id=user.id, entity=entity, entity_id=entity_id)
        session.add(entry)
    entry.folder, entry.tags = body.folder.strip(), body.tags
    session.commit()
    return {"folder": entry.folder, "tags": entry.tags}


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    path: str = Field(max_length=2000)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value):
        parts = urlsplit(value)
        if parts.scheme or parts.netloc or parts.path not in ("/documentos", "/registros", "/busca", "/pessoas", "/organizar"):
            raise ValueError("Busca deve apontar para uma lista do Legível")
        return value


@router.get("/saved-searches")
def saved_searches(user: Viewer, session: SessionDep) -> list[dict]:
    return [
        {"id": item.id, "name": item.name, "path": item.path}
        for item in session.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.id))
    ]


@router.post("/saved-searches", status_code=201)
def save_search(body: SavedSearchIn, user: Viewer, session: SessionDep) -> dict:
    item = SavedSearch(user_id=user.id, name=body.name.strip(), path=body.path)
    session.add(item)
    session.commit()
    return {"id": item.id, "name": item.name, "path": item.path}


@router.delete("/saved-searches/{search_id}", status_code=204)
def delete_search(search_id: int, user: Viewer, session: SessionDep) -> Response:
    item = session.get(SavedSearch, search_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Busca não encontrada")
    session.delete(item)
    session.commit()
    return Response(status_code=204)


class RedactionRegion(BaseModel):
    page_id: int
    rect: list[float] = Field(min_length=4, max_length=4)

    @field_validator("rect")
    @classmethod
    def rectangle(cls, value):
        import math

        x0, y0, x1, y1 = value
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in value) or x0 >= x1 or y0 >= y1:
            raise ValueError("Retângulo inválido")
        return value


class RedactionIn(BaseModel):
    regions: list[RedactionRegion] = Field(min_length=1, max_length=500)
    preview_page: int | None = None


@router.post("/redaction/{entity}/{entity_id}")
def export_redacted(
    entity: str, entity_id: int, body: RedactionIn, user: Viewer, session: SessionDep, store: StoreDep
) -> Response:
    check_entity(session, entity, entity_id)
    item = load_document(session, entity_id) if entity == "document" else session.get(Record, entity_id)
    pages = [image for image in item.images if image.kind == "page"] if entity == "document" else item.pages
    page_ids = {page.id for page in pages}
    if any(region.page_id not in page_ids for region in body.regions) or (
        body.preview_page and body.preview_page not in page_ids
    ):
        raise HTTPException(400, "Página não pertence ao documento")
    rendered = []
    for page in pages:
        if body.preview_page and body.preview_page != page.id:
            continue
        source = page.processed_path or page.original_path
        if not source:
            raise HTTPException(400, "Este registro não guarda imagens")
        regions = [region.rect for region in body.regions if region.page_id == page.id]
        rendered.append(redacted_image(store.load(source), regions))
    if not rendered:
        raise HTTPException(400, "Nenhuma página para exportar")
    audit(session, user.id, "export", entity, entity_id, "prévia ocultada" if body.preview_page else "PDF ocultado")
    session.commit()
    if body.preview_page:
        return Response(rendered[0], media_type="image/png", headers={"Cache-Control": "no-store"})
    return Response(
        redacted_pdf(rendered),
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="legivel-{entity_id}-ocultado.pdf"'},
    )
