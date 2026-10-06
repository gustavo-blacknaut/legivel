from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from legivel.auth import totp
from legivel.auth.one_time import consume, find_active, issue_token, revoke_pending
from legivel.auth.passwords import check_password_policy, hash_password, needs_rehash, verify_password
from legivel.auth.tokens import as_aware, revoke_all
from legivel.db.base import utc_now
from legivel.db.models import TokenPurpose, User, UserRole, UserToken
from legivel.security.sealing import seal, unseal
from legivel.services.audit import record
from legivel.services.settings import RuntimeSettings


class AccountError(ValueError):
    pass


@dataclass(frozen=True)
class LoginOutcome:
    user: User | None
    status: str
    locked_until: datetime | None = None
    account_id: int | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def has_users(session: Session) -> bool:
    return bool(session.scalar(select(func.count(User.id))))


def find_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalize_email(email)))


def apply_password(user: User, password: str, runtime: RuntimeSettings) -> None:
    check_password_policy(password, runtime.password_min_length, runtime.password_require_mixed, user.email)
    user.password_hash = hash_password(password)
    user.password_changed_at = utc_now()


def create_user(
    session: Session,
    email: str,
    password: str,
    runtime: RuntimeSettings,
    role: str = UserRole.ADMIN,
    name: str = "",
    verified: bool = True,
) -> User:
    email = normalize_email(email)
    user = find_by_email(session, email)
    if user is None:
        user = User(email=email, name=name.strip(), role=role, recovery_codes=[])
        session.add(user)
    elif name:
        user.name = name.strip()
    apply_password(user, password, runtime)
    user.role = role
    user.is_active = True
    user.failed_logins = 0
    user.locked_until = None
    if verified and user.email_verified_at is None:
        user.email_verified_at = utc_now()
    session.flush()
    return user


def create_first_admin(session: Session, email: str, name: str, password: str, runtime: RuntimeSettings) -> User:
    if has_users(session):
        raise AccountError("O sistema já foi configurado.")
    user = create_user(session, email, password, runtime, UserRole.ADMIN, name, verified=False)
    record(session, user.id, "setup", "user", user.id, "primeiro administrador")
    return user


def is_locked(user: User) -> bool:
    return user.locked_until is not None and as_aware(user.locked_until) > utc_now()


def authenticate(session: Session, email: str, password: str, runtime: RuntimeSettings) -> LoginOutcome:
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is not None and is_locked(user):
        verify_password(None, password)
        return LoginOutcome(None, "locked", user.locked_until, user.id)
    if not verify_password(user.password_hash if user else None, password):
        if user is not None:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= runtime.login_max_attempts:
                user.failed_logins = 0
                user.locked_until = utc_now() + timedelta(minutes=runtime.login_lock_minutes)
                record(session, user.id, "lock", "user", user.id, f"bloqueado por {runtime.login_lock_minutes} min")
                return LoginOutcome(None, "locked", user.locked_until, user.id)
        return LoginOutcome(None, "invalid", account_id=user.id if user else None)
    if not user.is_active:
        return LoginOutcome(None, "disabled", account_id=user.id)
    user.failed_logins = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return LoginOutcome(user, "ok")


def mark_login(user: User) -> None:
    user.last_login_at = utc_now()


def change_password(session: Session, user: User, current: str, new: str, runtime: RuntimeSettings) -> None:
    if not verify_password(user.password_hash, current):
        raise AccountError("Senha atual incorreta.")
    if current == new:
        raise AccountError("A nova senha precisa ser diferente da atual.")
    apply_password(user, new, runtime)
    record(session, user.id, "password_change", "user", user.id)


def invite(
    session: Session, email: str, role: str, inviter: User, runtime: RuntimeSettings
) -> tuple[UserToken, str]:
    email = normalize_email(email)
    if role not in tuple(UserRole):
        raise AccountError("Papel desconhecido.")
    if find_by_email(session, email) is not None:
        raise AccountError("Já existe uma conta com este e-mail.")
    revoke_pending(session, TokenPurpose.INVITE, email)
    token, raw = issue_token(
        session, TokenPurpose.INVITE, email, timedelta(hours=runtime.invite_hours), role=role, created_by=inviter.id
    )
    record(session, inviter.id, "invite", "invitation", token.id, f"papel {role}")
    return token, raw


def invitation(session: Session, raw_token: str) -> UserToken:
    return find_active(session, TokenPurpose.INVITE, raw_token)


def accept_invite(session: Session, raw_token: str, name: str, password: str, runtime: RuntimeSettings) -> User:
    token = invitation(session, raw_token)
    if find_by_email(session, token.email) is not None:
        consume(token)
        raise AccountError("Já existe uma conta com este e-mail.")
    user = User(email=token.email, name=name.strip(), role=token.role or UserRole.READER, recovery_codes=[])
    apply_password(user, password, runtime)
    user.email_verified_at = utc_now()
    session.add(user)
    consume(token)
    session.flush()
    record(session, user.id, "invite_accept", "user", user.id, f"papel {user.role}")
    return user


def revoke_invite(session: Session, token: UserToken, admin: User) -> None:
    token.revoked_at = utc_now()
    record(session, admin.id, "invite_revoke", "invitation", token.id)


def request_reset(session: Session, email: str, runtime: RuntimeSettings, minutes: int) -> tuple[User, str] | None:
    user = find_by_email(session, email)
    if user is None or not user.is_active:
        return None
    revoke_pending(session, TokenPurpose.RESET_PASSWORD, user.email)
    _, raw = issue_token(session, TokenPurpose.RESET_PASSWORD, user.email, timedelta(minutes=minutes), user_id=user.id)
    record(session, user.id, "reset_request", "user", user.id)
    return user, raw


def reset_password(session: Session, raw_token: str, password: str, runtime: RuntimeSettings) -> User:
    token = find_active(session, TokenPurpose.RESET_PASSWORD, raw_token)
    user = session.get(User, token.user_id) if token.user_id else None
    if user is None or not user.is_active:
        consume(token)
        raise AccountError("Conta não encontrada ou desativada.")
    apply_password(user, password, runtime)
    user.failed_logins = 0
    user.locked_until = None
    if user.email_verified_at is None and user.email == token.email:
        user.email_verified_at = utc_now()
    consume(token)
    revoke_all(session, user.id)
    record(session, user.id, "password_reset", "user", user.id)
    return user


def issue_verification(session: Session, user: User, email: str, hours: int) -> str:
    revoke_pending(session, TokenPurpose.VERIFY_EMAIL, email)
    _, raw = issue_token(session, TokenPurpose.VERIFY_EMAIL, email, timedelta(hours=hours), user_id=user.id)
    return raw


def request_email_change(session: Session, user: User, email: str, password: str, hours: int) -> str:
    email = normalize_email(email)
    if not verify_password(user.password_hash, password):
        raise AccountError("Senha incorreta.")
    if email == user.email:
        raise AccountError("Este já é o seu e-mail.")
    if find_by_email(session, email) is not None:
        raise AccountError("Já existe uma conta com este e-mail.")
    user.pending_email = email
    record(session, user.id, "email_change_request", "user", user.id)
    return issue_verification(session, user, email, hours)


def confirm_email(session: Session, raw_token: str) -> User:
    token = find_active(session, TokenPurpose.VERIFY_EMAIL, raw_token)
    user = session.get(User, token.user_id) if token.user_id else None
    if user is None:
        consume(token)
        raise AccountError("Conta não encontrada.")
    if token.email != user.email:
        if user.pending_email != token.email or find_by_email(session, token.email) is not None:
            consume(token)
            raise AccountError("Este pedido de troca de e-mail não é mais válido.")
        user.email = token.email
        user.pending_email = None
        record(session, user.id, "email_change", "user", user.id)
    user.email_verified_at = utc_now()
    consume(token)
    record(session, user.id, "email_verify", "user", user.id)
    return user


def begin_two_factor(user: User, secret_key: str, issuer: str) -> tuple[str, str]:
    if user.two_factor_enabled:
        raise AccountError("A verificação em duas etapas já está ativa.")
    secret = totp.new_secret()
    user.totp_secret = seal(secret_key, secret)
    uri = totp.provisioning_uri(secret, user.email, issuer)
    return secret, uri


def confirm_two_factor(session: Session, user: User, secret_key: str, code: str) -> list[str]:
    if user.two_factor_enabled or not user.totp_secret:
        raise AccountError("Comece a configuração da verificação em duas etapas novamente.")
    if not totp.verify_code(unseal(secret_key, user.totp_secret), code):
        raise AccountError("Código incorreto. Confira o horário do celular e tente de novo.")
    codes = totp.new_recovery_codes()
    user.recovery_codes = [totp.hash_recovery_code(secret_key, item) for item in codes]
    user.totp_enabled_at = utc_now()
    record(session, user.id, "2fa_enable", "user", user.id)
    return codes


def check_second_factor(session: Session, user: User, secret_key: str, code: str) -> bool:
    if not user.two_factor_enabled or not user.totp_secret:
        return True
    if totp.verify_code(unseal(secret_key, user.totp_secret), code):
        return True
    remaining = list(user.recovery_codes or [])
    matched = totp.find_recovery_code(remaining, secret_key, code)
    if matched is not None:
        remaining.remove(matched)
        user.recovery_codes = remaining
        record(session, user.id, "2fa_recovery_code", "user", user.id, f"{len(remaining)} código(s) restante(s)")
        return True
    return False


def disable_two_factor(session: Session, user: User, password: str, actor: User | None = None) -> None:
    if actor is None and not verify_password(user.password_hash, password):
        raise AccountError("Senha incorreta.")
    user.totp_secret = None
    user.totp_enabled_at = None
    user.recovery_codes = []
    record(session, (actor or user).id, "2fa_disable", "user", user.id)


def update_user(session: Session, admin: User, user: User, role: str | None, is_active: bool | None) -> None:
    if user.id == admin.id and (role not in (None, UserRole.ADMIN) or is_active is False):
        raise AccountError("Você não pode remover o seu próprio acesso de administrador.")
    if role is not None:
        if role not in tuple(UserRole):
            raise AccountError("Papel desconhecido.")
        if role != user.role:
            record(session, admin.id, "role_change", "user", user.id, f"{user.role} para {role}")
            user.role = role
    if is_active is not None and is_active != user.is_active:
        user.is_active = is_active
        if not is_active:
            revoke_all(session, user.id)
        record(session, admin.id, "user_enable" if is_active else "user_disable", "user", user.id)
    if is_active and is_locked(user):
        user.locked_until = None
    remaining_admins = session.scalar(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    )
    if not remaining_admins:
        raise AccountError("O sistema precisa de pelo menos um administrador ativo.")
