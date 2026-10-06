import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from legivel.auth.tokens import as_aware, hash_token
from legivel.db.base import utc_now
from legivel.db.models import TokenPurpose, UserToken

TOKEN_BYTES = 32


class InvalidTokenError(ValueError):
    pass


def issue_token(
    session: Session,
    purpose: TokenPurpose,
    email: str,
    lifetime: timedelta,
    user_id: int | None = None,
    role: str | None = None,
    created_by: int | None = None,
) -> tuple[UserToken, str]:
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    token = UserToken(
        purpose=purpose,
        token_hash=hash_token(raw_token),
        email=email,
        role=role,
        user_id=user_id,
        created_by=created_by,
        expires_at=utc_now() + lifetime,
    )
    session.add(token)
    session.flush()
    return token, raw_token


def revoke_pending(session: Session, purpose: TokenPurpose, email: str) -> None:
    session.execute(
        update(UserToken)
        .where(
            UserToken.purpose == purpose,
            UserToken.email == email,
            UserToken.used_at.is_(None),
            UserToken.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )


def token_state(token: UserToken) -> str:
    if token.used_at is not None:
        return "used"
    if token.revoked_at is not None:
        return "revoked"
    if as_aware(token.expires_at) <= utc_now():
        return "expired"
    return "active"


def find_active(session: Session, purpose: TokenPurpose, raw_token: str) -> UserToken:
    token = session.scalar(
        select(UserToken).where(UserToken.purpose == purpose, UserToken.token_hash == hash_token(raw_token))
    )
    if token is None or token_state(token) != "active":
        raise InvalidTokenError("Este link é inválido, já foi usado ou expirou.")
    return token


def consume(token: UserToken) -> None:
    token.used_at = utc_now()
