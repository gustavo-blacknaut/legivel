import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from legivel.security.crypto import EncryptionKeyError, KeyRing, decode_key

ENV_PREFIX = "LEGIVEL_"
SECRET_FILE_SUFFIX = "_FILE"
MINIMUM_SECRET_LENGTH = 32
UPLOAD_FORMATS = ("jpeg", "png", "webp", "heic")
INTERFACE_LANGUAGES = ("pt-BR", "en")
THEMES = ("system", "light", "dark")


class ConfigurationError(SystemExit):
    pass


class OcrSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix=ENV_PREFIX, extra="ignore")

    ocr_engine: Literal["rapidocr", "tesseract"] = "rapidocr"
    ocr_device: Literal["auto", "cpu", "gpu"] = "auto"
    ocr_languages: str = "por"
    ocr_model_dir: Path = Path("./models")


class Settings(OcrSettings):
    production: bool = False
    database_url: str = "sqlite:///./data/legivel.db"
    database_password: str = ""
    secret_key: str = ""
    encryption_enabled: bool = True
    encryption_key: str = ""
    encryption_old_keys: str = ""
    storage_dir: Path = Path("./storage")
    public_url: str = ""

    smtp_host: str = ""
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    ocr_warmup: bool = True
    ocr_passes: int = Field(3, ge=1, le=4)
    background_jobs: bool = True

    upload_max_mb: int = Field(15, ge=1, le=100)
    upload_formats: str = ",".join(UPLOAD_FORMATS)
    image_quality: int = Field(88, ge=40, le=100)
    compress_originals: bool = False
    original_max_side: int = Field(3000, ge=800, le=10000)

    retention_days: int = Field(0, ge=0)
    retention_interval_hours: int = Field(24, ge=1)

    password_min_length: int = Field(10, ge=8, le=128)
    argon2_time_cost: int = Field(3, ge=2, le=20)
    argon2_memory_kib: int = Field(65536, ge=19456, le=1048576)
    argon2_parallelism: int = Field(4, ge=1, le=16)
    password_require_mixed: bool = True
    login_max_attempts: int = Field(5, ge=1, le=100)
    login_lock_minutes: int = Field(15, ge=1)
    access_minutes: int = Field(15, ge=1, le=1440)
    refresh_days: int = Field(30, ge=1, le=365)
    session_idle_hours: int = Field(12, ge=1, le=720)
    invite_hours: int = Field(72, ge=1, le=720)
    reset_minutes: int = Field(60, ge=5, le=1440)
    verify_hours: int = Field(48, ge=1, le=720)
    scan_link_hours: int = Field(48, ge=1, le=720)
    secure_cookies: bool = False

    instance_name: str = Field("Legível", min_length=1, max_length=60)
    default_theme: Literal["system", "light", "dark"] = "system"
    default_language: Literal["pt-BR", "en"] = "pt-BR"
    timezone: str = "America/Sao_Paulo"

    @field_validator("secret_key")
    @classmethod
    def secret_is_long_enough(cls, value: str) -> str:
        if len(value) < MINIMUM_SECRET_LENGTH:
            raise ValueError(
                f"obrigatória, com pelo menos {MINIMUM_SECRET_LENGTH} caracteres (gere com: python -m legivel.cli generate-key)"
            )
        return value

    @field_validator("database_url")
    @classmethod
    def database_is_supported(cls, value: str) -> str:
        if not value.startswith(("sqlite:///", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("use sqlite:///caminho.db ou postgresql+psycopg://usuario:senha@host:5432/banco")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @field_validator("upload_formats")
    @classmethod
    def formats_are_known(cls, value: str) -> str:
        formats = [item.strip().lower() for item in value.split(",") if item.strip()]
        unknown = sorted(set(formats) - set(UPLOAD_FORMATS))
        if not formats or unknown:
            raise ValueError(f"formatos aceitos: {', '.join(UPLOAD_FORMATS)}; recebido: {value!r}")
        return ",".join(dict.fromkeys(formats))

    @field_validator("public_url")
    @classmethod
    def public_url_is_absolute(cls, value: str) -> str:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("precisa começar com http:// ou https://, por exemplo http://192.168.0.10:8090")
        return value.rstrip("/")

    @model_validator(mode="after")
    def encryption_key_is_valid(self) -> "Settings":
        if self.encryption_enabled:
            try:
                decode_key(self.encryption_key)
                for key in self.previous_keys:
                    decode_key(key)
            except EncryptionKeyError as error:
                raise ValueError(
                    f"LEGIVEL_ENCRYPTION_KEY: {error}. Gere com python -m legivel.cli generate-key"
                    " ou defina LEGIVEL_ENCRYPTION_ENABLED=false"
                ) from error
        if self.database_password and not self.is_sqlite:
            url = make_url(self.database_url).set(password=self.database_password)
            self.database_url = url.render_as_string(hide_password=False)
        if self.smtp_host and not self.smtp_from:
            raise ValueError("LEGIVEL_SMTP_FROM: obrigatório quando LEGIVEL_SMTP_HOST está definido")
        if self.production:
            self.refuse_insecure_production()
        return self

    def refuse_insecure_production(self) -> None:
        problems = []
        if not self.secure_cookies:
            problems.append("LEGIVEL_SECURE_COOKIES=true")
        if not self.public_url.startswith("https://"):
            problems.append("LEGIVEL_PUBLIC_URL com https://")
        if not self.encryption_enabled:
            problems.append("LEGIVEL_ENCRYPTION_ENABLED=true")
        if self.smtp_host and self.smtp_security == "none":
            problems.append("LEGIVEL_SMTP_SECURITY starttls ou ssl")
        if problems:
            raise ValueError("LEGIVEL_PRODUCTION: em produção é obrigatório " + ", ".join(problems))

    @property
    def previous_keys(self) -> list[str]:
        return [key.strip() for key in self.encryption_old_keys.split(",") if key.strip()]

    def key_ring(self) -> KeyRing | None:
        return KeyRing(self.encryption_key, self.previous_keys) if self.encryption_enabled else None

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host)

    @property
    def allowed_formats(self) -> tuple[str, ...]:
        return tuple(self.upload_formats.split(","))

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def describe_errors(error: ValidationError) -> str:
    lines = ["Configuração inválida:"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        name = f"{ENV_PREFIX}{location.upper()}" if location else ""
        message = item["msg"].removeprefix("Value error, ")
        lines.append(f"  - {name}: {message}" if name else f"  - {message}")
    return "\n".join(lines)


def read_secret_files(environment: Mapping[str, str]) -> dict[str, str]:
    values = {}
    for name in Settings.model_fields:
        variable = f"{ENV_PREFIX}{name.upper()}"
        path = environment.get(variable + SECRET_FILE_SUFFIX)
        if not path or environment.get(variable):
            continue
        try:
            values[name] = Path(path).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ConfigurationError(
                f"Configuração inválida:\n  - {variable}{SECRET_FILE_SUFFIX}: não foi possível ler {path} ({error.strerror})"
            ) from None
    return values


def load_settings(**overrides) -> Settings:
    try:
        return Settings(**{**read_secret_files(os.environ), **overrides})
    except ValidationError as error:
        raise ConfigurationError(describe_errors(error)) from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
