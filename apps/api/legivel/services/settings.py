import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from zoneinfo import available_timezones

from sqlalchemy import select
from sqlalchemy.orm import Session

from legivel.auth.permissions import ROLE_DEFAULTS, editable_roles, normalize_permissions
from legivel.config import INTERFACE_LANGUAGES, THEMES, UPLOAD_FORMATS, Settings
from legivel.db.models import AppSetting

ROLE_PERMISSIONS_KEY = "role_permissions"
LOGO_PATH_KEY = "logo_path"
LOGO_MIME_KEY = "logo_mime"
OCR_DEVICES = ("auto", "cpu", "gpu")


class SettingError(ValueError):
    pass


@dataclass(frozen=True)
class Option:
    key: str
    kind: str
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] = field(default_factory=tuple)


OPTIONS = (
    Option("instance_name", "str", 1, 60),
    Option("default_theme", "choice", choices=THEMES),
    Option("default_language", "choice", choices=INTERFACE_LANGUAGES),
    Option("timezone", "timezone"),
    Option("ocr_device", "choice", choices=OCR_DEVICES),
    Option("ocr_passes", "int", 1, 4),
    Option("upload_max_mb", "int", 1, 100),
    Option("upload_formats", "formats"),
    Option("image_quality", "int", 40, 100),
    Option("compress_originals", "bool"),
    Option("retention_days", "int", 0, 36500),
    Option("password_min_length", "int", 8, 128),
    Option("password_require_mixed", "bool"),
    Option("login_max_attempts", "int", 1, 100),
    Option("login_lock_minutes", "int", 1, 1440),
    Option("refresh_days", "int", 1, 365),
    Option("session_idle_hours", "int", 1, 720),
    Option("invite_hours", "int", 1, 720),
    Option("scan_link_hours", "int", 1, 720),
)
OPTIONS_BY_KEY = {option.key: option for option in OPTIONS}


@lru_cache
def valid_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def convert(option: Option, value: Any) -> Any:
    if option.kind == "bool":
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "sim"):
            return True
        if str(value).lower() in ("false", "0", "não", "nao"):
            return False
        raise SettingError(f"{option.key}: use verdadeiro ou falso")
    if option.kind == "int":
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise SettingError(f"{option.key}: precisa ser um número inteiro") from error
        if (option.minimum is not None and number < option.minimum) or (option.maximum is not None and number > option.maximum):
            raise SettingError(f"{option.key}: precisa estar entre {option.minimum} e {option.maximum}")
        return number
    text = str(value).strip()
    if option.kind == "str":
        if not option.minimum <= len(text) <= option.maximum:
            raise SettingError(f"{option.key}: precisa ter entre {option.minimum} e {option.maximum} caracteres")
        return text
    if option.kind == "choice":
        if text not in option.choices:
            raise SettingError(f"{option.key}: escolha entre {', '.join(option.choices)}")
        return text
    if option.kind == "timezone":
        if text not in valid_timezones():
            raise SettingError(f"Fuso horário desconhecido: {text}")
        return text
    if option.kind == "formats":
        formats = [item.strip().lower() for item in text.split(",") if item.strip()]
        if not formats or set(formats) - set(UPLOAD_FORMATS):
            raise SettingError(f"upload_formats: escolha entre {', '.join(UPLOAD_FORMATS)}")
        return ",".join(dict.fromkeys(formats))
    raise SettingError(f"Configuração desconhecida: {option.key}")


@dataclass(frozen=True)
class RuntimeSettings:
    values: dict[str, Any]
    role_permissions: dict[str, list[str]]
    logo_path: str | None
    logo_mime: str | None
    overridden: frozenset[str]

    def __getattr__(self, name: str) -> Any:
        try:
            return self.values[name]
        except KeyError as error:
            raise AttributeError(name) from error

    @property
    def allowed_formats(self) -> tuple[str, ...]:
        return tuple(self.values["upload_formats"].split(","))

    def permissions_of(self, role: str) -> frozenset[str]:
        if role not in self.role_permissions:
            return frozenset()
        return frozenset(self.role_permissions[role])


def stored_values(session: Session) -> dict[str, str]:
    return {setting.key: setting.value for setting in session.scalars(select(AppSetting))}


def load_runtime(session: Session, settings: Settings) -> RuntimeSettings:
    stored = stored_values(session)
    values = {}
    overridden = set()
    for option in OPTIONS:
        default = getattr(settings, option.key)
        if option.key in stored:
            try:
                values[option.key] = convert(option, stored[option.key])
                overridden.add(option.key)
                continue
            except SettingError:
                pass
        values[option.key] = default
    permissions = {role: sorted(defaults) for role, defaults in ROLE_DEFAULTS.items()}
    if ROLE_PERMISSIONS_KEY in stored:
        try:
            saved = json.loads(stored[ROLE_PERMISSIONS_KEY])
            for role in editable_roles():
                if role in saved:
                    permissions[role] = normalize_permissions(saved[role])
        except (ValueError, TypeError):
            pass
    return RuntimeSettings(values, permissions, stored.get(LOGO_PATH_KEY), stored.get(LOGO_MIME_KEY), frozenset(overridden))


def write_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key)
    if setting is None:
        session.add(AppSetting(key=key, value=value))
    else:
        setting.value = value


def remove_setting(session: Session, key: str) -> None:
    setting = session.get(AppSetting, key)
    if setting is not None:
        session.delete(setting)


def update_runtime(session: Session, changes: dict[str, Any]) -> list[str]:
    changed = []
    for key, value in changes.items():
        option = OPTIONS_BY_KEY.get(key)
        if option is None:
            raise SettingError(f"Configuração desconhecida ou que não pode ser alterada em execução: {key}")
        if value is None:
            remove_setting(session, key)
            changed.append(f"{key}: padrão")
            continue
        converted = convert(option, value)
        write_setting(session, key, json.dumps(converted) if option.kind == "bool" else str(converted))
        changed.append(f"{key}: {converted}")
    return changed


def update_role_permissions(session: Session, permissions: dict[str, list[str]]) -> None:
    unknown = set(permissions) - set(editable_roles())
    if unknown:
        raise SettingError(f"Papéis que não podem ser alterados: {', '.join(sorted(unknown))}")
    current = {role: sorted(defaults) for role, defaults in ROLE_DEFAULTS.items() if role in editable_roles()}
    current.update({role: normalize_permissions(values) for role, values in permissions.items()})
    write_setting(session, ROLE_PERMISSIONS_KEY, json.dumps(current))


def set_logo(session: Session, path: str | None, mime: str | None) -> None:
    if path is None:
        remove_setting(session, LOGO_PATH_KEY)
        remove_setting(session, LOGO_MIME_KEY)
        return
    write_setting(session, LOGO_PATH_KEY, path)
    write_setting(session, LOGO_MIME_KEY, mime or "image/png")
