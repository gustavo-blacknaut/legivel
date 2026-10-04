from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GREEN_OCR_", extra="ignore")

    database_url: str = "sqlite:///./data/green_ocr.db"
    storage_dir: Path = Path("./storage")
    encryption_key: str = Field(default="", description="Chave AES-256 em base64 urlsafe (32 bytes)")
    secret_key: str = ""
    ocr_engine: str = "paddle"
    ocr_device: str = "cpu"
    access_minutes: int = 15
    refresh_days: int = 30
    scan_link_hours: int = 48
    secure_cookies: bool = False
    max_upload_mb: int = 15
    frontend_dir: Path = Path("./frontend/dist")


@lru_cache
def get_settings() -> Settings:
    return Settings()
