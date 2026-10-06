import logging
import time
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from legivel.auth import accounts, totp
from legivel.auth.accounts import AccountError
from legivel.auth.one_time import InvalidTokenError, token_state
from legivel.auth.passwords import WeakPasswordError
from legivel.auth.permissions import Permission
from legivel.auth.schemas import (
    AcceptInviteIn,
    AccountOut,
    AccountUpdateIn,
    DeliveryOut,
    EmailChangeIn,
    ForgotIn,
    InvitationCreated,
    InvitationIn,
    InvitationOut,
    InvitationPreview,
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    PasswordIn,
    ProfileIn,
    RecoveryCodesOut,
    ResetIn,
    SessionOut,
    SetupIn,
    TokenIn,
    TwoFactorIn,
    TwoFactorSetupOut,
    UserOut,
)
from legivel.auth.tokens import (
    active_sessions,
    hash_token,
    issue_refresh_token,
    revoke_all,
    revoke_other_sessions,
    revoke_refresh_token,
    revoke_session,
    rotate_refresh_token,
)
from legivel.db.models import RefreshToken, TokenPurpose, User, UserToken
from legivel.mail.messages import compose
from legivel.mail.sender import MailError, OutgoingMail
from legivel.services.audit import record
from legivel.services.settings import RuntimeSettings
from legivel.web.deps import RuntimeDep, SessionDep, UserDep, require

logger = logging.getLogger("legivel.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])
setup_router = APIRouter(prefix="/api/setup", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])
PUBLIC_API_PATHS = (
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/password/forgot",
    "/api/auth/password/reset",
    "/api/auth/invitations/",
    "/api/auth/email/verify",
    "/api/public/",
    "/api/setup",
    "/health",
)
LOGIN_FAILED = "E-mail ou senha inválidos. Depois de várias tentativas seguidas a conta fica bloqueada por alguns minutos."
REFRESH_COOKIE = "legivel_refresh"
REFRESH_PATH = "/"
TWO_FACTOR_SECONDS = 300
TWO_FACTOR_ATTEMPTS = 5
INVITE_PATH = "/convite/"
VERIFY_PATH = "/verificar-email/"
RESET_PATH = "/redefinir-senha/"
AdminDep = Annotated[User, Depends(require(Permission.USERS_MANAGE))]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def public_base(request: Request) -> str:
    configured = request.app.state.settings.public_url
    if configured:
        return configured
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{scheme}://{host.split(',')[0].strip()}"


def format_moment(moment: datetime, runtime: RuntimeSettings) -> str:
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo(runtime.timezone)).strftime("%d/%m/%Y %H:%M")


def outgoing(
    request: Request, runtime: RuntimeSettings, kind: str, to: str, link: str, expires_at: datetime, **values: str
) -> OutgoingMail | None:
    if not request.app.state.mailer.configured:
        return None
    return compose(
        kind, runtime.default_language, to, link, instance=runtime.instance_name,
        expires=format_moment(expires_at, runtime), **values,
    )


def send_quietly(mailer, mail: OutgoingMail, sender: str) -> None:
    try:
        mailer.send(mail, sender)
    except MailError:
        return


def deliver(
    request: Request, runtime: RuntimeSettings, kind: str, to: str, link: str, expires_at: datetime, **values: str
) -> bool:
    mail = outgoing(request, runtime, kind, to, link, expires_at, **values)
    if mail is None:
        return False
    try:
        request.app.state.mailer.send(mail, runtime.instance_name)
    except MailError:
        return False
    return True


def user_out(user: User, runtime: RuntimeSettings) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        permissions=sorted(runtime.permissions_of(user.role)),
        email_verified=user.email_verified_at is not None,
        pending_email=user.pending_email,
        two_factor_enabled=user.two_factor_enabled,
    )


def set_refresh_cookie(request: Request, response: Response, raw_token: str, runtime: RuntimeSettings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=runtime.refresh_days * 24 * 60 * 60,
        path=REFRESH_PATH,
        httponly=True,
        samesite="strict",
        secure=request.app.state.settings.secure_cookies,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)


def start_session(request: Request, response: Response, session: Session, user: User, runtime: RuntimeSettings) -> UserOut:
    token, raw_token = issue_refresh_token(
        session, user, runtime.refresh_days, request.headers.get("user-agent"), client_ip(request)
    )
    accounts.mark_login(user)
    record(session, user.id, "login", "user", user.id)
    session.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["sid"] = token.id
    set_refresh_cookie(request, response, raw_token, runtime)
    return user_out(user, runtime)


def guard_ip(request: Request, scope: str) -> str:
    key = f"{scope}:{client_ip(request) or 'unknown'}"
    if request.app.state.login_throttle.is_blocked(key):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    return key


@router.post("/login")
def login(request: Request, response: Response, credentials: LoginIn, session: SessionDep, runtime: RuntimeDep) -> LoginOut:
    throttle = request.app.state.login_throttle
    key = guard_ip(request, "login")
    outcome = accounts.authenticate(session, credentials.email, credentials.password, runtime)
    if outcome.user is None:
        throttle.record_failure(key)
        record(session, None, "login_failed", "user", outcome.account_id, outcome.status)
        session.commit()
        raise HTTPException(401, LOGIN_FAILED)
    user = outcome.user
    if user.two_factor_enabled:
        session.commit()
        request.session.clear()
        request.session["pending_user"] = user.id
        request.session["pending_at"] = int(time.time())
        request.session["pending_attempts"] = 0
        return LoginOut(status="two_factor")
    throttle.reset(key)
    return LoginOut(status="ok", user=start_session(request, response, session, user, runtime))


@router.post("/login/two-factor")
def login_two_factor(
    request: Request, response: Response, payload: TwoFactorIn, session: SessionDep, runtime: RuntimeDep
) -> LoginOut:
    key = guard_ip(request, "2fa")
    user_id = request.session.get("pending_user")
    started = request.session.get("pending_at", 0)
    if not user_id or time.time() - started > TWO_FACTOR_SECONDS:
        request.session.clear()
        raise HTTPException(401, "O tempo para informar o código acabou. Entre novamente.")
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(401, "Entre novamente.")
    if not accounts.check_second_factor(session, user, request.app.state.settings.secret_key, payload.code):
        request.app.state.login_throttle.record_failure(key)
        attempts = request.session.get("pending_attempts", 0) + 1
        record(session, user.id, "2fa_failed", "user", user.id)
        session.commit()
        if attempts >= TWO_FACTOR_ATTEMPTS:
            request.session.clear()
            raise HTTPException(401, "Código incorreto várias vezes. Entre novamente.")
        request.session["pending_attempts"] = attempts
        raise HTTPException(400, "Código incorreto.")
    return LoginOut(status="ok", user=start_session(request, response, session, user, runtime))


@router.post("/refresh")
def refresh(request: Request, response: Response, session: SessionDep, runtime: RuntimeDep) -> UserOut:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    rotated = (
        rotate_refresh_token(
            session,
            raw_token,
            runtime.refresh_days,
            runtime.session_idle_hours,
            request.headers.get("user-agent"),
            client_ip(request),
        )
        if raw_token
        else None
    )
    if rotated is None:
        request.session.clear()
        clear_refresh_cookie(response)
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    user, token, new_token = rotated
    session.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["sid"] = token.id
    set_refresh_cookie(request, response, new_token, runtime)
    return user_out(user, runtime)


@router.get("/me")
def me(user: UserDep, runtime: RuntimeDep) -> UserOut:
    return user_out(user, runtime)


@router.post("/logout", status_code=204)
def logout(request: Request, session: SessionDep) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if raw_token:
        revoke_refresh_token(session, raw_token)
    user_id = request.session.get("user_id")
    if user_id:
        record(session, user_id, "logout", "user", user_id)
    session.commit()
    request.session.clear()
    response = Response(status_code=204)
    clear_refresh_cookie(response)
    return response


@router.post("/password/forgot", status_code=202)
def forgot_password(
    request: Request, payload: ForgotIn, session: SessionDep, runtime: RuntimeDep, background: BackgroundTasks
) -> dict[str, str]:
    key = guard_ip(request, "forgot")
    request.app.state.login_throttle.record_failure(key)
    settings = request.app.state.settings
    issued = accounts.request_reset(session, payload.email, runtime, settings.reset_minutes)
    if issued is not None:
        user, raw = issued
        token = session.scalar(select(UserToken).where(UserToken.token_hash == hash_token(raw)))
        mail = outgoing(request, runtime, "reset", user.email, f"{public_base(request)}{RESET_PATH}{raw}", token.expires_at)
        if mail is not None:
            background.add_task(send_quietly, request.app.state.mailer, mail, runtime.instance_name)
    session.commit()
    return {"detail": "Se o e-mail estiver cadastrado, enviaremos um link para redefinir a senha."}


@router.post("/password/reset")
def reset_password(request: Request, payload: ResetIn, session: SessionDep, runtime: RuntimeDep) -> dict[str, str]:
    guard_ip(request, "reset")
    try:
        accounts.reset_password(session, payload.token, payload.password, runtime)
    except (InvalidTokenError, AccountError, WeakPasswordError) as error:
        session.commit()
        request.app.state.login_throttle.record_failure(f"reset:{client_ip(request) or 'unknown'}")
        raise HTTPException(400, str(error)) from error
    session.commit()
    return {"detail": "Senha redefinida. Entre com a nova senha."}


@router.get("/invitations/{token}")
def preview_invitation(request: Request, token: str, session: SessionDep) -> InvitationPreview:
    key = guard_ip(request, "invite")
    try:
        invitation = accounts.invitation(session, token)
    except InvalidTokenError as error:
        request.app.state.login_throttle.record_failure(key)
        raise HTTPException(404, str(error)) from error
    return InvitationPreview(email=invitation.email, role=invitation.role or "reader", expires_at=invitation.expires_at)


@router.post("/invitations/{token}/accept")
def accept_invitation(
    request: Request, response: Response, token: str, payload: AcceptInviteIn, session: SessionDep, runtime: RuntimeDep
) -> UserOut:
    key = guard_ip(request, "invite")
    try:
        user = accounts.accept_invite(session, token, payload.name, payload.password, runtime)
    except (InvalidTokenError, AccountError, WeakPasswordError) as error:
        session.commit()
        if isinstance(error, InvalidTokenError):
            request.app.state.login_throttle.record_failure(key)
        raise HTTPException(400, str(error)) from error
    return start_session(request, response, session, user, runtime)


@router.post("/email/verify")
def verify_email(request: Request, payload: TokenIn, session: SessionDep, runtime: RuntimeDep) -> dict[str, str]:
    key = guard_ip(request, "verify")
    try:
        user = accounts.confirm_email(session, payload.token)
    except (InvalidTokenError, AccountError) as error:
        session.commit()
        request.app.state.login_throttle.record_failure(key)
        raise HTTPException(400, str(error)) from error
    session.commit()
    return {"detail": f"E-mail {user.email} confirmado."}


@router.post("/email/resend")
def resend_verification(request: Request, user: UserDep, session: SessionDep, runtime: RuntimeDep) -> DeliveryOut:
    target = user.pending_email or user.email
    if user.email_verified_at is not None and not user.pending_email:
        return DeliveryOut(emailed=False, detail="Seu e-mail já está confirmado.")
    raw = accounts.issue_verification(session, user, target, request.app.state.settings.verify_hours)
    token = session.scalar(select(UserToken).where(UserToken.token_hash == hash_token(raw)))
    emailed = deliver(request, runtime, "verify", target, f"{public_base(request)}{VERIFY_PATH}{raw}", token.expires_at)
    session.commit()
    if not emailed:
        return DeliveryOut(emailed=False, detail="Não foi possível enviar o e-mail. Verifique a configuração de SMTP.")
    return DeliveryOut(emailed=True, detail=f"Enviamos um link de confirmação para {target}.")


@router.put("/profile")
def update_profile(payload: ProfileIn, user: UserDep, session: SessionDep, runtime: RuntimeDep) -> UserOut:
    user.name = payload.name.strip()
    record(session, user.id, "profile_update", "user", user.id)
    session.commit()
    return user_out(user, runtime)


@router.post("/password")
def change_password(request: Request, payload: PasswordChangeIn, user: UserDep, session: SessionDep, runtime: RuntimeDep) -> dict:
    try:
        accounts.change_password(session, user, payload.current_password, payload.new_password, runtime)
    except (AccountError, WeakPasswordError) as error:
        session.commit()
        raise HTTPException(400, str(error)) from error
    revoked = revoke_other_sessions(session, user.id, request.cookies.get(REFRESH_COOKIE))
    session.commit()
    return {"detail": "Senha alterada.", "revoked_sessions": revoked}


@router.post("/email")
def change_email(
    request: Request, payload: EmailChangeIn, user: UserDep, session: SessionDep, runtime: RuntimeDep
) -> DeliveryOut:
    hours = request.app.state.settings.verify_hours
    try:
        raw = accounts.request_email_change(session, user, payload.email, payload.password, hours)
    except AccountError as error:
        session.commit()
        raise HTTPException(400, str(error)) from error
    token = session.scalar(select(UserToken).where(UserToken.token_hash == hash_token(raw)))
    emailed = deliver(request, runtime, "verify", payload.email, f"{public_base(request)}{VERIFY_PATH}{raw}", token.expires_at)
    session.commit()
    if not emailed:
        return DeliveryOut(emailed=False, detail="Pedido registrado, mas o e-mail não foi enviado. Verifique o SMTP.")
    return DeliveryOut(emailed=True, detail=f"Enviamos um link para {payload.email}. O e-mail muda depois da confirmação.")


def to_session_out(token: RefreshToken, current_hash: str | None) -> SessionOut:
    return SessionOut(
        id=token.id,
        user_agent=token.user_agent,
        ip_address=token.ip_address,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        expires_at=token.expires_at,
        current=token.token_hash == current_hash,
    )


@router.get("/sessions")
def sessions(request: Request, user: UserDep, session: SessionDep) -> list[SessionOut]:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    current_hash = hash_token(raw_token) if raw_token else None
    return [to_session_out(token, current_hash) for token in active_sessions(session, user.id)]


@router.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: int, user: UserDep, session: SessionDep) -> Response:
    if not revoke_session(session, user.id, session_id):
        raise HTTPException(404, "Sessão não encontrada")
    record(session, user.id, "revoke", "session", session_id)
    session.commit()
    return Response(status_code=204)


@router.post("/sessions/revoke-others")
def revoke_others(request: Request, user: UserDep, session: SessionDep) -> dict[str, int]:
    revoked = revoke_other_sessions(session, user.id, request.cookies.get(REFRESH_COOKIE))
    record(session, user.id, "revoke", "session", None, f"{revoked} sessão(ões) encerrada(s)")
    session.commit()
    return {"revoked": revoked}


@router.post("/two-factor/setup")
def two_factor_setup(request: Request, user: UserDep, session: SessionDep, runtime: RuntimeDep) -> TwoFactorSetupOut:
    try:
        secret, uri = accounts.begin_two_factor(user, request.app.state.settings.secret_key, runtime.instance_name)
    except AccountError as error:
        raise HTTPException(400, str(error)) from error
    session.commit()
    return TwoFactorSetupOut(secret=secret, uri=uri, qr_svg=totp.qr_svg(uri))


@router.post("/two-factor/confirm")
def two_factor_confirm(request: Request, payload: TwoFactorIn, user: UserDep, session: SessionDep) -> RecoveryCodesOut:
    try:
        codes = accounts.confirm_two_factor(session, user, request.app.state.settings.secret_key, payload.code)
    except AccountError as error:
        raise HTTPException(400, str(error)) from error
    session.commit()
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/two-factor/disable", status_code=204)
def two_factor_disable(payload: PasswordIn, user: UserDep, session: SessionDep) -> Response:
    try:
        accounts.disable_two_factor(session, user, payload.password)
    except AccountError as error:
        raise HTTPException(400, str(error)) from error
    session.commit()
    return Response(status_code=204)


@setup_router.get("")
def setup_status(session: SessionDep) -> dict[str, bool]:
    return {"required": not accounts.has_users(session)}


@setup_router.post("", status_code=201)
def run_setup(request: Request, response: Response, payload: SetupIn, session: SessionDep, runtime: RuntimeDep) -> UserOut:
    guard_ip(request, "setup")
    try:
        user = accounts.create_first_admin(session, payload.email, payload.name, payload.password, runtime)
    except (AccountError, WeakPasswordError) as error:
        session.rollback()
        raise HTTPException(409 if isinstance(error, AccountError) else 400, str(error)) from error
    raw = accounts.issue_verification(session, user, user.email, request.app.state.settings.verify_hours)
    token = session.scalar(select(UserToken).where(UserToken.token_hash == hash_token(raw)))
    deliver(request, runtime, "verify", user.email, f"{public_base(request)}{VERIFY_PATH}{raw}", token.expires_at)
    return start_session(request, response, session, user, runtime)


def account_out(session: Session, user: User) -> AccountOut:
    sessions_count = len(active_sessions(session, user.id))
    return AccountOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        email_verified=user.email_verified_at is not None,
        two_factor_enabled=user.two_factor_enabled,
        locked=accounts.is_locked(user),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        sessions=sessions_count,
    )


def invitation_out(session: Session, token: UserToken) -> InvitationOut:
    inviter = session.get(User, token.created_by) if token.created_by else None
    return InvitationOut(
        id=token.id,
        email=token.email,
        role=token.role or "reader",
        state=token_state(token),
        created_at=token.created_at,
        expires_at=token.expires_at,
        invited_by=inviter.display_name if inviter else None,
    )


def load_account(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Usuário não encontrado")
    return user


@users_router.get("")
def list_accounts(admin: AdminDep, session: SessionDep) -> list[AccountOut]:
    users = session.scalars(select(User).order_by(func.lower(User.name), User.email)).all()
    return [account_out(session, user) for user in users]


@users_router.patch("/{user_id}")
def update_account(user_id: int, payload: AccountUpdateIn, admin: AdminDep, session: SessionDep) -> AccountOut:
    user = load_account(session, user_id)
    try:
        accounts.update_user(session, admin, user, payload.role, payload.is_active)
    except AccountError as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error
    if payload.unlock and user.locked_until is not None:
        user.locked_until = None
        user.failed_logins = 0
        record(session, admin.id, "unlock", "user", user.id)
    session.commit()
    return account_out(session, user)


@users_router.post("/{user_id}/reset-link")
def account_reset_link(request: Request, user_id: int, admin: AdminDep, session: SessionDep, runtime: RuntimeDep) -> DeliveryOut:
    user = load_account(session, user_id)
    issued = accounts.request_reset(session, user.email, runtime, request.app.state.settings.reset_minutes)
    if issued is None:
        raise HTTPException(400, "A conta está desativada.")
    _, raw = issued
    token = session.scalar(select(UserToken).where(UserToken.token_hash == hash_token(raw)))
    link = f"{public_base(request)}{RESET_PATH}{raw}"
    emailed = deliver(request, runtime, "reset", user.email, link, token.expires_at)
    record(session, admin.id, "reset_link", "user", user.id, "enviado por e-mail" if emailed else "link gerado")
    session.commit()
    detail = f"Link enviado para {user.email}." if emailed else "SMTP indisponível. Copie o link e envie à pessoa."
    return DeliveryOut(emailed=emailed, link=None if emailed else link, detail=detail)


@users_router.post("/{user_id}/revoke-sessions")
def account_revoke_sessions(user_id: int, admin: AdminDep, session: SessionDep) -> dict[str, int]:
    user = load_account(session, user_id)
    count = len(active_sessions(session, user.id))
    revoke_all(session, user.id)
    record(session, admin.id, "revoke", "user", user.id, f"{count} sessão(ões)")
    session.commit()
    return {"revoked": count}


@users_router.delete("/{user_id}/two-factor", status_code=204)
def account_disable_two_factor(user_id: int, admin: AdminDep, session: SessionDep) -> Response:
    user = load_account(session, user_id)
    accounts.disable_two_factor(session, user, "", actor=admin)
    session.commit()
    return Response(status_code=204)


@users_router.get("/invitations")
def list_invitations(admin: AdminDep, session: SessionDep) -> list[InvitationOut]:
    tokens = session.scalars(
        select(UserToken).where(UserToken.purpose == TokenPurpose.INVITE).order_by(UserToken.created_at.desc()).limit(100)
    ).all()
    return [invitation_out(session, token) for token in tokens]


@users_router.post("/invitations", status_code=201)
def create_invitation(
    request: Request, payload: InvitationIn, admin: AdminDep, session: SessionDep, runtime: RuntimeDep
) -> InvitationCreated:
    try:
        token, raw = accounts.invite(session, payload.email, payload.role, admin, runtime)
    except AccountError as error:
        session.rollback()
        raise HTTPException(400, str(error)) from error
    link = f"{public_base(request)}{INVITE_PATH}{raw}"
    emailed = deliver(
        request, runtime, "invite", token.email, link, token.expires_at, inviter=admin.display_name, role=payload.role
    )
    session.commit()
    detail = f"Convite enviado para {token.email}." if emailed else "SMTP indisponível. Copie o link e envie à pessoa."
    return InvitationCreated(emailed=emailed, link=link, detail=detail, invitation=invitation_out(session, token))


@users_router.delete("/invitations/{invitation_id}", status_code=204)
def cancel_invitation(invitation_id: int, admin: AdminDep, session: SessionDep) -> Response:
    token = session.get(UserToken, invitation_id)
    if token is None or token.purpose != TokenPurpose.INVITE:
        raise HTTPException(404, "Convite não encontrado")
    if token_state(token) == "active":
        accounts.revoke_invite(session, token, admin)
        session.commit()
    return Response(status_code=204)
