import logging
import threading
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from legivel.config import Settings
from legivel.db.base import utc_now
from legivel.db.models import Document, ScanLink, UserToken
from legivel.services.audit import record
from legivel.services.documents import delete_document
from legivel.services.settings import load_runtime
from legivel.storage.file_store import FileStore

logger = logging.getLogger("legivel.retention")
BATCH_SIZE = 200
TOKEN_KEEP_DAYS = 30


def purge_expired_documents(session: Session, store: FileStore, days: int) -> int:
    if days <= 0:
        return 0
    cutoff = utc_now() - timedelta(days=days)
    removed = 0
    while True:
        documents = session.scalars(
            select(Document).where(Document.processed_at < cutoff).order_by(Document.id).limit(BATCH_SIZE)
        ).all()
        if not documents:
            break
        for document in documents:
            delete_document(session, store, document, None)
            removed += 1
    if removed:
        record(session, None, "retention", "document", None, f"{removed} documento(s) com mais de {days} dia(s)")
        session.commit()
    return removed


def purge_stale_tokens(session: Session) -> None:
    cutoff = utc_now() - timedelta(days=TOKEN_KEEP_DAYS)
    for token in session.scalars(select(UserToken).where(UserToken.expires_at < cutoff)):
        session.delete(token)
    for link in session.scalars(select(ScanLink).where(ScanLink.expires_at < cutoff, ScanLink.document_id.is_(None))):
        session.delete(link)
    session.commit()


def run_retention(factory: sessionmaker[Session], store: FileStore, settings: Settings) -> int:
    with factory() as session:
        runtime = load_runtime(session, settings)
        removed = purge_expired_documents(session, store, runtime.retention_days)
        purge_stale_tokens(session)
    if removed:
        logger.info("Retenção: %s documento(s) excluído(s)", removed)
    return removed


def start_retention_worker(factory: sessionmaker[Session], store: FileStore, settings: Settings) -> threading.Event:
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            try:
                run_retention(factory, store, settings)
            except Exception:
                logger.exception("Falha na exclusão automática")
            stop.wait(settings.retention_interval_hours * 3600)

    threading.Thread(target=loop, daemon=True, name="retention").start()
    return stop
