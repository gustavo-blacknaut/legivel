from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.orm import Session

from legivel.db.models import AuditLog

current_ip: ContextVar[str | None] = ContextVar("current_ip", default=None)
MAX_DETAILS_LENGTH = 255


@event.listens_for(AuditLog, "before_insert")
def fill_ip_address(_mapper, _connection, target: AuditLog) -> None:
    if target.ip_address is None:
        target.ip_address = current_ip.get()


def record(
    session: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    details: str | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details[:MAX_DETAILS_LENGTH] if details else None,
        )
    )
