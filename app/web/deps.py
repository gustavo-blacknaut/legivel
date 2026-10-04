from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.ocr.base import OcrEngine
from app.ocr.factory import get_ocr_engine
from app.storage.encrypted_store import EncryptedFileStore


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_store(request: Request) -> EncryptedFileStore:
    return request.app.state.store


def get_engine(request: Request) -> OcrEngine:
    override = getattr(request.app.state, "ocr_engine", None)
    return override or get_ocr_engine(request.app.state.settings.ocr_engine, request.app.state.settings.ocr_device)
