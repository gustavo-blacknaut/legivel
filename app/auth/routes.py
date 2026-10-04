from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.auth.tokens import (
    active_sessions,
    hash_token,
    issue_refresh_token,
    revoke_other_sessions,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.auth.users import authenticate
from app.db.models import RefreshToken, User
from app.services.audit import record
from app.web.deps import get_session
from app.web.schemas import Credentials, SessionOut, UserOut

router = APIRouter(prefix="/api/auth")
PUBLIC_API_PATHS = ("/api/auth/login", "/api/auth/me", "/api/auth/refresh", "/api/public/", "/health")
REFRESH_COOKIE = "lince_refresh"
REFRESH_PATH = "/api/auth"
SessionDep = Annotated[Session, Depends(get_session)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def client_key(request: Request, username: str) -> str:
    return f"{client_ip(request) or 'unknown'}:{username.lower()}"


def set_refresh_cookie(request: Request, response: Response, raw_token: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.refresh_days * 24 * 60 * 60,
        path=REFRESH_PATH,
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
    )


def start_session(request: Request, response: Response, session: Session, user: User) -> UserOut:
    settings = request.app.state.settings
    raw_token = issue_refresh_token(session, user, settings.refresh_days, request.headers.get("user-agent"), client_ip(request))
    session.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    set_refresh_cookie(request, response, raw_token)
    return UserOut(id=user.id, username=user.username)


@router.post("/login")
def login(request: Request, response: Response, credentials: Credentials, session: SessionDep) -> UserOut:
    throttle = request.app.state.login_throttle
    key = client_key(request, credentials.username)
    if throttle.is_blocked(key):
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos.")
    user = authenticate(session, credentials.username.strip(), credentials.password)
    if user is None:
        throttle.record_failure(key)
        record(session, None, "login_failed", "user", None, f"usuário informado: {credentials.username.strip()[:60]}")
        session.commit()
        raise HTTPException(401, "Usuário ou senha inválidos.")
    throttle.reset(key)
    return start_session(request, response, session, user)


@router.post("/refresh")
def refresh(request: Request, response: Response, session: SessionDep) -> UserOut:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    settings = request.app.state.settings
    rotated = (
        rotate_refresh_token(session, raw_token, settings.refresh_days, request.headers.get("user-agent"), client_ip(request))
        if raw_token
        else None
    )
    if rotated is None:
        request.session.clear()
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    user, new_token = rotated
    session.commit()
    request.session.clear()
    request.session["user_id"] = user.id
    set_refresh_cookie(request, response, new_token)
    return UserOut(id=user.id, username=user.username)


@router.get("/me")
def me(request: Request, session: SessionDep) -> UserOut:
    user_id = request.session.get("user_id")
    user = session.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(401, "Não autenticado")
    return UserOut(id=user.id, username=user.username)


@router.post("/logout", status_code=204)
def logout(request: Request, session: SessionDep) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if raw_token:
        revoke_refresh_token(session, raw_token)
    record(session, request.session.get("user_id"), "logout", "user", request.session.get("user_id"))
    session.commit()
    request.session.clear()
    response = Response(status_code=204)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return response


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
def sessions(request: Request, session: SessionDep) -> list[SessionOut]:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    current_hash = hash_token(raw_token) if raw_token else None
    return [to_session_out(token, current_hash) for token in active_sessions(session, request.session["user_id"])]


@router.post("/sessions/revoke-others")
def revoke_others(request: Request, session: SessionDep) -> dict[str, int]:
    user_id = request.session["user_id"]
    revoked = revoke_other_sessions(session, user_id, request.cookies.get(REFRESH_COOKIE))
    record(session, user_id, "revoke", "session", None, f"{revoked} sessão(ões) encerrada(s)")
    session.commit()
    return {"revoked": revoked}
