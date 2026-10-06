import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from legivel import __version__
from legivel.auth.passwords import configure_hashing
from legivel.auth.routes import PUBLIC_API_PATHS, setup_router, users_router
from legivel.auth.routes import router as auth_router
from legivel.auth.throttle import LoginThrottle
from legivel.config import Settings, get_settings
from legivel.db.session import build_engine, build_session_factory
from legivel.mail.sender import Mailer
from legivel.ocr.factory import get_ocr_engine
from legivel.security.fields import configure_fields
from legivel.services.audit import current_ip
from legivel.services.jobs import start_worker
from legivel.services.retention import start_retention_worker
from legivel.services.settings import load_runtime
from legivel.storage.file_store import FileStore
from legivel.web.limits import BodySizeLimit
from legivel.web.maintenance_routes import router as maintenance_router
from legivel.web.modules_routes import router as records_router
from legivel.web.product_routes import router as product_router
from legivel.web.routes import public_router, router
from legivel.web.workflow_routes import router as workflow_router

CSRF_HEADER = "x-requested-with"
CSRF_HEADER_VALUE = "legivel"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
IP_ATTEMPTS = 20
SESSION_COOKIE = "legivel_session"


def configure_logging() -> None:
    logger = logging.getLogger("legivel")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def validation_problems(error: RequestValidationError) -> list[dict]:
    return [{"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]} for item in error.errors()]


async def reject_invalid_request(_request: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse({"detail": validation_problems(error)}, status_code=422)


def warm_up_ocr(application: FastAPI) -> None:
    settings = application.state.settings
    try:
        with application.state.session_factory() as session:
            device = load_runtime(session, settings).ocr_device
        get_ocr_engine(settings.ocr_engine, device, settings.ocr_model_dir, settings.ocr_languages)
    except Exception:
        logging.getLogger("legivel.ocr").exception("Falha ao preparar o motor de OCR")


ROUTERS = (
    setup_router,
    auth_router,
    users_router,
    router,
    records_router,
    public_router,
    workflow_router,
    maintenance_router,
    product_router,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    from legivel.services.backups import apply_pending_restore

    apply_pending_restore(settings)
    configure_logging()
    ring = settings.key_ring()
    configure_fields(ring, settings.secret_key)
    configure_hashing(settings.argon2_time_cost, settings.argon2_memory_kib, settings.argon2_parallelism)

    @asynccontextmanager
    async def lifespan(app):
        worker = start_worker(app) if settings.background_jobs else None
        try:
            yield
        finally:
            if worker:
                worker[0].set()
                worker[1].join(timeout=30)

    application = FastAPI(
        title="Legível", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    application.state.settings = settings
    application.state.maintenance_lock = threading.RLock()
    application.state.session_factory = build_session_factory(build_engine(settings.database_url))
    application.state.store = FileStore(settings.storage_dir, ring)
    application.state.login_throttle = LoginThrottle(max_attempts=IP_ATTEMPTS)
    application.state.mailer = Mailer(settings)
    application.add_exception_handler(RequestValidationError, reject_invalid_request)
    for item in ROUTERS:
        application.include_router(item)

    @application.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.background_jobs:
        start_retention_worker(
            application.state.session_factory,
            application.state.store,
            settings,
            lambda: getattr(application.state, "restore_pending", False),
        )
        if settings.ocr_warmup:
            threading.Thread(target=warm_up_ocr, args=(application,), daemon=True, name="ocr-warmup").start()

    @application.middleware("http")
    async def protect_api(request: Request, call_next):
        path = request.url.path
        current_ip.set(request.client.host if request.client else None)
        if path.startswith("/api/"):
            paused = getattr(application.state, "restore_pending", False)
            if paused and request.method not in SAFE_METHODS and not path.startswith(("/api/maintenance", "/api/auth")):
                return JSONResponse(
                    {"detail": "Gravações pausadas para restauração. Reinicie a API ou cancele no painel."}, status_code=503
                )
            if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
                return JSONResponse({"detail": "Requisição recusada"}, status_code=403)
            if not path.startswith(PUBLIC_API_PATHS) and not request.session.get("user_id"):
                return JSONResponse({"detail": "Não autenticado"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if path.startswith("/api/") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=SESSION_COOKIE,
        max_age=settings.access_minutes * 60,
        same_site="strict",
        https_only=settings.secure_cookies,
    )
    application.add_middleware(BodySizeLimit)
    return application


def openapi_document() -> dict:
    from fastapi.openapi.utils import get_openapi

    application = FastAPI(title="Legível", version=__version__)
    for item in ROUTERS:
        application.include_router(item)
    return get_openapi(title="Legível", version=__version__, routes=application.routes)
