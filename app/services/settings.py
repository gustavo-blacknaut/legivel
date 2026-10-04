from functools import lru_cache
from zoneinfo import available_timezones

from sqlalchemy.orm import Session

from app.db.models import AppSetting

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
