import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from legivel.db.base import utc_now
from legivel.db.models import RefreshToken, User

TOKEN_BYTES = 32
USER_AGENT_LENGTH = 255


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def issue_refresh_token(
    session: Session,
    user: User,
    days: int,
    user_agent: str | None,
    ip: str | None,
    started_at: datetime | None = None,
) -> tuple[RefreshToken, str]:
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    started = as_aware(started_at) if started_at else utc_now()
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        user_agent=(user_agent or "")[:USER_AGENT_LENGTH] or None,
        ip_address=ip,
        started_at=started,
        expires_at=started + timedelta(days=days),
    )
    session.add(token)
    session.flush()
    return token, raw_token


def revoke_all(session: Session, user_id: int) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def rotate_refresh_token(
    session: Session, raw_token: str, days: int, idle_hours: int, user_agent: str | None, ip: str | None
) -> tuple[User, RefreshToken, str] | None:
    token = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is None:
        return None
    if token.revoked_at is not None:
        revoke_all(session, token.user_id)
        session.commit()
        return None
    user = session.get(User, token.user_id)
    now = utc_now()
    started = as_aware(token.started_at or token.created_at)
    expired = as_aware(token.expires_at) <= now or started + timedelta(days=days) <= now
    idle = as_aware(token.created_at) + timedelta(hours=idle_hours) <= now
    if expired or idle or user is None or not user.is_active:
        token.revoked_at = now
        session.commit()
        return None
    token.revoked_at = now
    new_token, raw = issue_refresh_token(session, user, days, user_agent or token.user_agent, ip, started)
    return user, new_token, raw


def revoke_refresh_token(session: Session, raw_token: str) -> None:
    token = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is not None and token.revoked_at is None:
        token.revoked_at = utc_now()


def active_sessions(session: Session, user_id: int) -> list[RefreshToken]:
    tokens = session.scalars(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .order_by(RefreshToken.created_at.desc())
    ).all()
    now = utc_now()
    return [token for token in tokens if as_aware(token.expires_at) > now]


def revoke_other_sessions(session: Session, user_id: int, current_raw_token: str | None) -> int:
    keep = hash_token(current_raw_token) if current_raw_token else None
    tokens = active_sessions(session, user_id)
    revoked = 0
    for token in tokens:
        if token.token_hash != keep:
            token.revoked_at = utc_now()
            revoked += 1
    return revoked


def is_session_active(session: Session, user_id: int, token_id: int | None) -> bool:
    if token_id is None:
        return False
    token = session.get(RefreshToken, token_id)
    return (
        token is not None
        and token.user_id == user_id
        and token.revoked_at is None
        and as_aware(token.expires_at) > utc_now()
    )


def revoke_session(session: Session, user_id: int, token_id: int) -> bool:
    token = session.get(RefreshToken, token_id)
    if token is None or token.user_id != user_id or token.revoked_at is not None:
        return False
    token.revoked_at = utc_now()
    return True
