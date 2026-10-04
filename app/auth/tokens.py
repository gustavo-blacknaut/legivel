import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import RefreshToken, User

TOKEN_BYTES = 32
USER_AGENT_LENGTH = 255


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def issue_refresh_token(session: Session, user: User, days: int, user_agent: str | None, ip: str | None) -> str:
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            user_agent=(user_agent or "")[:USER_AGENT_LENGTH] or None,
            ip_address=ip,
            expires_at=utc_now() + timedelta(days=days),
        )
    )
    return raw_token


def revoke_all(session: Session, user_id: int) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


def rotate_refresh_token(
    session: Session, raw_token: str, days: int, user_agent: str | None, ip: str | None
) -> tuple[User, str] | None:
    token = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is None:
        return None
    if token.revoked_at is not None:
        revoke_all(session, token.user_id)
        session.commit()
        return None
    user = session.get(User, token.user_id)
    if as_aware(token.expires_at) <= utc_now() or user is None or not user.is_active:
        token.revoked_at = utc_now()
        session.commit()
        return None
    token.revoked_at = utc_now()
    new_token = issue_refresh_token(session, user, days, user_agent or token.user_agent, ip)
    return user, new_token


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
