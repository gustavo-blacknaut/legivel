from enum import StrEnum

from legivel.db.models import UserRole


class Permission(StrEnum):
    DOCUMENTS_VIEW = "documents.view"
    DOCUMENTS_UPLOAD = "documents.upload"
    DOCUMENTS_REVIEW = "documents.review"
    DOCUMENTS_DELETE = "documents.delete"
    IMAGES_ORIGINAL = "images.original"
    DATA_REVEAL = "data.reveal"
    PEOPLE_EDIT = "people.edit"
    PEOPLE_DELETE = "people.delete"
    SCAN_LINKS = "scan_links.manage"
    AUDIT_VIEW = "audit.view"
    USERS_MANAGE = "users.manage"
    SETTINGS_MANAGE = "settings.manage"


ADMIN_ONLY = frozenset({Permission.USERS_MANAGE, Permission.SETTINGS_MANAGE})
ROLE_DEFAULTS: dict[str, frozenset[str]] = {
    UserRole.ADMIN: frozenset(Permission),
    UserRole.REVIEWER: frozenset(
        {
            Permission.DOCUMENTS_VIEW,
            Permission.DOCUMENTS_UPLOAD,
            Permission.DOCUMENTS_REVIEW,
            Permission.DOCUMENTS_DELETE,
            Permission.IMAGES_ORIGINAL,
            Permission.DATA_REVEAL,
            Permission.PEOPLE_EDIT,
            Permission.SCAN_LINKS,
        }
    ),
    UserRole.READER: frozenset({Permission.DOCUMENTS_VIEW}),
}


def editable_roles() -> tuple[str, ...]:
    return (UserRole.REVIEWER, UserRole.READER)


def assignable_permissions() -> list[str]:
    return [permission.value for permission in Permission if permission not in ADMIN_ONLY]


def normalize_permissions(values) -> list[str]:
    allowed = set(assignable_permissions())
    return sorted({str(value) for value in values if str(value) in allowed} | {Permission.DOCUMENTS_VIEW.value})
