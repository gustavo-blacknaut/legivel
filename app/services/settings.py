from functools import lru_cache
from zoneinfo import available_timezones

from sqlalchemy.orm import Session

from app.db.models import AppSetting
from app.ocr.languages import AUTO, LANGUAGES

TIMEZONE_KEY = "timezone"
DEFAULT_TIMEZONE = "America/Sao_Paulo"


@lru_cache
def valid_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def get_setting(session: Session, key: str, default: str) -> str:
    setting = session.get(AppSetting, key)
    return setting.value if setting else default


def set_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key)
    if setting is None:
        session.add(AppSetting(key=key, value=value))
    else:
        setting.value = value


def get_timezone(session: Session) -> str:
    return get_setting(session, TIMEZONE_KEY, DEFAULT_TIMEZONE)


def set_timezone(session: Session, timezone: str) -> None:
    if timezone not in valid_timezones():
        raise ValueError(f"Fuso horário desconhecido: {timezone}")
    set_setting(session, TIMEZONE_KEY, timezone)


LANGUAGES_KEY = "languages"
DEFAULT_LANGUAGE_KEY = "default_language"
CARD_STORAGE_KEY = "store_card_numbers"
DEFAULT_LANGUAGES = ["pt", "en", "es"]


def get_languages(session: Session) -> list[str]:
    raw = get_setting(session, LANGUAGES_KEY, ",".join(DEFAULT_LANGUAGES))
    return [code for code in raw.split(",") if code in LANGUAGES] or list(DEFAULT_LANGUAGES)


def set_languages(session: Session, codes: list[str]) -> None:
    valid = [code for code in dict.fromkeys(codes) if code in LANGUAGES]
    if not valid:
        raise ValueError("Escolha pelo menos um idioma")
    set_setting(session, LANGUAGES_KEY, ",".join(valid))


def get_default_language(session: Session) -> str:
    value = get_setting(session, DEFAULT_LANGUAGE_KEY, AUTO)
    return value if value == AUTO or value in LANGUAGES else AUTO


def set_default_language(session: Session, code: str) -> None:
    if code != AUTO and code not in LANGUAGES:
        raise ValueError(f"Idioma desconhecido: {code}")
    set_setting(session, DEFAULT_LANGUAGE_KEY, code)


def get_card_storage(session: Session) -> bool:
    return get_setting(session, CARD_STORAGE_KEY, "0") == "1"


def set_card_storage(session: Session, enabled: bool) -> None:
    set_setting(session, CARD_STORAGE_KEY, "1" if enabled else "0")
