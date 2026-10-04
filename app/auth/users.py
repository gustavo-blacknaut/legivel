from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.db.models import AuditLog, User, UserRole

MINIMUM_PASSWORD_LENGTH = 10


def create_user(session: Session, username: str, password: str, role: str = UserRole.ADMIN) -> User:
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValueError(f"A senha precisa ter pelo menos {MINIMUM_PASSWORD_LENGTH} caracteres")
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, role=role)
        session.add(user)
    user.password_hash = hash_password(password)
    user.is_active = True
    session.commit()
    return user


def authenticate(session: Session, username: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if not verify_password(user.password_hash if user else None, password):
        return None
    session.add(AuditLog(user_id=user.id, action="login", entity="user", entity_id=user.id))
    session.commit()
    return user
