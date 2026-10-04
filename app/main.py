from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth.routes import PUBLIC_API_PATHS
from app.auth.routes import router as auth_router
from app.auth.throttle import LoginThrottle
from app.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory
from app.security.crypto import FileCipher
from app.services.audit import current_ip
from app.storage.encrypted_store import EncryptedFileStore
from app.web.modules_routes import router as modules_router
from app.web.routes import public_router, router

MINIMUM_SECRET_LENGTH = 32
CSRF_HEADER = "x-requested-with"
CSRF_HEADER_VALUE = "lince"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class MissingSecretKeyError(ValueError):
    pass


def mount_frontend(application: FastAPI, frontend_dir: Path) -> None:
    index = frontend_dir / "index.html"
    if not index.exists():
        return
    if (frontend_dir / "assets").exists():
        application.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")

    @application.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (frontend_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(frontend_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    cipher = FileCipher(settings.encryption_key)
    if len(settings.secret_key) < MINIMUM_SECRET_LENGTH:
        raise MissingSecretKeyError(f"LINCE_SECRET_KEY precisa ter pelo menos {MINIMUM_SECRET_LENGTH} caracteres")
    application = FastAPI(title="Lince", docs_url=None, redoc_url=None, openapi_url=None)
    application.state.settings = settings
    application.state.session_factory = build_session_factory(build_engine(settings.database_url))
    application.state.store = EncryptedFileStore(settings.storage_dir, cipher)
    application.state.login_throttle = LoginThrottle()
    application.include_router(auth_router)
    application.include_router(router)
    application.include_router(public_router)
    application.include_router(modules_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_frontend(application, settings.frontend_dir)

    @application.middleware("http")
    async def protect_api(request: Request, call_next):
        path = request.url.path
        current_ip.set(request.client.host if request.client else None)
        if path.startswith("/api/"):
            if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
                return JSONResponse({"detail": "Requisição recusada"}, status_code=403)
            if not path.startswith(PUBLIC_API_PATHS) and not request.session.get("user_id"):
                return JSONResponse({"detail": "Não autenticado"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="lince_session",
        max_age=settings.access_minutes * 60,
        same_site="strict",
        https_only=settings.secure_cookies,
    )
    return application
