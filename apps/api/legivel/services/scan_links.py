import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from legivel.db.base import utc_now
from legivel.db.models import Document, ScanLink
from legivel.ocr.base import OcrEngine
from legivel.services.audit import record
from legivel.services.documents import DEFAULT_POLICY, ImagePolicy, UploadedSide, process_document
from legivel.storage.file_store import FileStore

TOKEN_BYTES = 24
MAX_LINK_HOURS = 24 * 14


class LinkState(StrEnum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class CreatedLink:
    link: ScanLink
    token: str


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def link_state(link: ScanLink) -> LinkState:
    if link.revoked_at is not None:
        return LinkState.REVOKED
    if link.used_at is not None:
        return LinkState.USED
    if as_aware(link.expires_at) <= utc_now():
        return LinkState.EXPIRED
    return LinkState.ACTIVE


def create_link(session: Session, user_id: int | None, label: str | None, hours: int) -> CreatedLink:
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    link = ScanLink(
        token_hash=hash_token(raw_token),
        label=(label or "").strip()[:120] or None,
        created_by=user_id,
        expires_at=utc_now() + timedelta(hours=max(1, min(hours, MAX_LINK_HOURS))),
    )
    session.add(link)
    session.flush()
    record(session, user_id, "create", "scan_link", link.id)
    session.commit()
    return CreatedLink(link, raw_token)


def list_links(session: Session, limit: int = 50) -> list[ScanLink]:
    return list(session.scalars(select(ScanLink).order_by(ScanLink.created_at.desc()).limit(limit)))


def revoke_link(session: Session, link: ScanLink, user_id: int | None) -> None:
    if link.revoked_at is None and link.used_at is None:
        link.revoked_at = utc_now()
        record(session, user_id, "revoke", "scan_link", link.id)
        session.commit()


def find_by_token(session: Session, raw_token: str) -> ScanLink | None:
    return session.scalar(select(ScanLink).where(ScanLink.token_hash == hash_token(raw_token)))


def submit_to_link(
    session: Session,
    store: FileStore,
    engine: OcrEngine,
    link: ScanLink,
    sides: list[UploadedSide],
    policy: ImagePolicy = DEFAULT_POLICY,
) -> Document:
    if link_state(link) != LinkState.ACTIVE:
        raise PermissionError("Este link não está mais disponível.")
    link.used_at = utc_now()
    session.commit()
    try:
        document = process_document(session, store, engine, None, sides, link.created_by, policy)
    except Exception:
        link.used_at = None
        session.commit()
        raise
    link.document_id = document.id
    record(session, None, "upload", "scan_link", link.id, f"documento #{document.id}")
    session.commit()
    return document
