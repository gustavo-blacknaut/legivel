import logging
import threading

from sqlalchemy import select, update

from legivel.auth.permissions import Permission
from legivel.db.models import Document, ProcessingJob, User
from legivel.modules.base import ProcessingContext
from legivel.modules.registry import get_module
from legivel.services.documents import ImagePolicy, UploadedSide, process_document
from legivel.services.records import CardPolicy, create_record
from legivel.services.settings import load_runtime
from legivel.web.deps import engine_for, pack_engines

logger = logging.getLogger(__name__)
def discard_files(store, paths):
    for path in paths:
        try:
            store.delete(path)
        except OSError:
            logger.warning("NÃ£o foi possÃ­vel limpar arquivo temporÃ¡rio")


class Cancelled(Exception):
    pass


class TrackedStore:
    def __init__(self, store):
        self.store = store
        self.paths = []

    def save(self, category, content):
        saved = self.store.save(category, content)
        self.paths.append(saved.relative_path)
        return saved

    def load(self, path):
        return self.store.load(path)

    def discard(self):
        discard_files(self.store, self.paths)


def process_next(application) -> bool:
    with application.state.maintenance_lock:
        if getattr(application.state, "restore_pending", False):
            return False
        factory = application.state.session_factory
        store = application.state.store
        with factory() as session:
            job_id = session.scalar(
                select(ProcessingJob.id).where(ProcessingJob.status == "queued").order_by(ProcessingJob.id).limit(1)
            )
            if job_id is None:
                return False
            claimed = session.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id, ProcessingJob.status == "queued")
                .values(status="running", error=None, completed_pages=0)
            )
            session.commit()
            if not claimed.rowcount:
                return True
            job = session.get(ProcessingJob, job_id)
            payload = job.payload
            user_id, module = job.user_id, job.module
    tracked = TrackedStore(store)
    completed = 0
    replaced_paths = []

    def progress():
        nonlocal completed
        with factory() as monitor:
            current = monitor.get(ProcessingJob, job_id)
            if current is None or current.status == "cancel_requested":
                raise Cancelled()
            completed = min(completed + 1, current.total_pages)
            current.completed_pages = completed
            monitor.commit()

    try:
        with factory() as session:
            user = session.get(User, user_id)
            runtime = load_runtime(session, application.state.settings)
            if not user or not user.is_active or Permission.DOCUMENTS_UPLOAD not in runtime.permissions_of(user.role):
                raise Cancelled()
            uploads = [store.load(path) for path in payload["paths"]]
            request = type("WorkerRequest", (), {"app": application})()
            if module == "documents":
                policy = ImagePolicy(
                    runtime.image_quality,
                    runtime.compress_originals,
                    application.state.settings.original_max_side,
                    runtime.ocr_passes,
                )
                result = process_document(
                    session,
                    tracked,
                    engine_for(request, runtime.ocr_device),
                    None,
                    [UploadedSide(side, data) for side, data in zip(payload["sides"], uploads, strict=True)],
                    user_id,
                    policy,
                    commit=False,
                    progress=progress,
                )
            else:
                context = ProcessingContext(
                    pack_engines(request, runtime.ocr_device),
                    runtime.reading_language_list,
                    payload.get("language") or runtime.default_reading_language,
                    payload.get("options", {}),
                    progress=progress,
                )
                result = create_record(
                    session,
                    tracked,
                    get_module(module),
                    context,
                    uploads,
                    user_id,
                    CardPolicy(runtime.store_card_numbers),
                    commit=False,
                )
            if payload.get("replace_id"):
                if Permission.DOCUMENTS_DELETE not in runtime.permissions_of(user.role):
                    raise Cancelled()
                previous = session.get(Document, payload["replace_id"])
                if previous:
                    replaced_paths = [
                        path
                        for image in previous.images
                        for path in (image.original_path, image.processed_path, image.thumbnail_path)
                        if path
                    ]
                    from legivel.services.audit import record as audit

                    audit(session, user_id, "delete", "document", previous.id, "substituÃ­do por nova leitura")
                    session.delete(previous)
            # Result and completion are committed together; recovery cannot create a second result.
            changed = session.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id, ProcessingJob.status == "running")
                .values(status="completed", result_id=result.id, completed_pages=len(uploads), payload={})
            )
            if not changed.rowcount:
                raise Cancelled()
            session.commit()
        discard_files(store, payload["paths"] + replaced_paths)
    except Exception as error:
        tracked.discard()
        with factory() as session:
            job = session.get(ProcessingJob, job_id)
            if job:
                cancelled = isinstance(error, Cancelled) or job.status == "cancel_requested"
                job.status = "cancelled" if cancelled else "failed"
                job.error = None if cancelled else "Falha na leitura. Tente novamente ou substitua a imagem."
                if cancelled:
                    job.payload = {}
                    discard_files(store, payload["paths"])
                session.commit()
        if not isinstance(error, Cancelled):
            logger.error("Falha na tarefa %s: %s", job_id, type(error).__name__)
    return True


def recover_jobs(application):
    with application.state.session_factory() as session:
        session.execute(update(ProcessingJob).where(ProcessingJob.status == "running").values(status="queued", completed_pages=0))
        cancelled = session.scalars(select(ProcessingJob).where(ProcessingJob.status == "cancel_requested")).all()
        for job in cancelled:
            discard_files(application.state.store, job.payload.get("paths", []))
            job.status, job.payload = "cancelled", {}
        session.commit()


def start_worker(application):
    stop = threading.Event()

    def run():
        recover_jobs(application)
        while not stop.is_set():
            try:
                if not process_next(application):
                    stop.wait(1)
            except Exception:
                logger.exception("Falha ao consultar fila")
                stop.wait(5)

    thread = threading.Thread(target=run, daemon=True, name="processing-queue")
    thread.start()
    return stop, thread
