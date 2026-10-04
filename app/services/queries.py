from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AuditLog, Document, DocumentStatus, Person, User
from app.validators.cpf import only_digits

MAX_PAGE_SIZE = 100
SORT_ORDERS = ("asc", "desc")


@dataclass(frozen=True)
class ListFilters:
    query: str = ""
    doc_type: str = ""
    status: str = ""
    created_from: date | None = None
    created_to: date | None = None
    sort: str = "date"
    order: str = "desc"
    page: int = 1
    page_size: int = 50

    @property
    def limit(self) -> int:
        return max(1, min(self.page_size, MAX_PAGE_SIZE))

    @property
    def offset(self) -> int:
        return (max(self.page, 1) - 1) * self.limit

    @property
    def descending(self) -> bool:
        return self.order != "asc"


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    total: int


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min)


def end_of(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min)


def text_condition(filters: ListFilters, name_column, cpf_column):
    term = filters.query.strip()
    if not term:
        return None
    conditions = [name_column.ilike(f"%{term}%")]
    digits = only_digits(term)
    if digits and not any(char.isalpha() for char in term):
        conditions.append(cpf_column.like(f"%{digits}%"))
    return or_(*conditions)


def date_conditions(filters: ListFilters, column) -> list:
    conditions = []
    if filters.created_from:
        conditions.append(column >= start_of(filters.created_from))
    if filters.created_to:
        conditions.append(column < end_of(filters.created_to))
    return conditions


def ordered(statement: Select, columns: list, descending: bool) -> Select:
    return statement.order_by(*[column.desc() if descending else column.asc() for column in columns])


def paginate(session: Session, statement: Select, filters: ListFilters) -> Page:
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    items = list(session.scalars(statement.limit(filters.limit).offset(filters.offset)).unique())
    return Page(items, total or 0)


def pending_documents_of_person():
    return exists().where(Document.person_id == Person.id, Document.status == DocumentStatus.PENDING_REVIEW)


def list_people(session: Session, filters: ListFilters) -> Page[Person]:
    statement = select(Person).options(selectinload(Person.documents).selectinload(Document.images))
    conditions = date_conditions(filters, Person.created_at)
    if (condition := text_condition(filters, Person.full_name, Person.cpf)) is not None:
        conditions.append(condition)
    if filters.doc_type:
        conditions.append(exists().where(Document.person_id == Person.id, Document.doc_type == filters.doc_type))
    if filters.status == DocumentStatus.PENDING_REVIEW:
        conditions.append(pending_documents_of_person())
    elif filters.status == DocumentStatus.REVIEWED:
        conditions.append(~pending_documents_of_person())
    if conditions:
        statement = statement.where(and_(*conditions))
    pending_rank = case((pending_documents_of_person(), 0), else_=1)
    sort_columns = {
        "name": [func.coalesce(Person.full_name, "")],
        "status": [pending_rank, Person.created_at],
        "date": [Person.created_at],
    }
    statement = ordered(statement, sort_columns.get(filters.sort, sort_columns["date"]), filters.descending)
    return paginate(session, statement.order_by(Person.id.desc()), filters)


def list_documents(session: Session, filters: ListFilters) -> Page[Document]:
    statement = select(Document).options(selectinload(Document.images))
    conditions = date_conditions(filters, Document.processed_at)
    if (condition := text_condition(filters, Document.full_name, Document.cpf)) is not None:
        conditions.append(condition)
    if filters.doc_type:
        conditions.append(Document.doc_type == filters.doc_type)
    if filters.status in (DocumentStatus.PENDING_REVIEW, DocumentStatus.REVIEWED):
        conditions.append(Document.status == filters.status)
    if conditions:
        statement = statement.where(and_(*conditions))
    sort_columns = {
        "name": [func.coalesce(Document.full_name, "")],
        "status": [Document.status, Document.processed_at],
        "date": [Document.processed_at],
    }
    statement = ordered(statement, sort_columns.get(filters.sort, sort_columns["date"]), filters.descending)
    return paginate(session, statement.order_by(Document.id.desc()), filters)


@dataclass(frozen=True)
class AuditEntry:
    id: int
    occurred_at: datetime
    username: str | None
    action: str
    entity: str
    entity_id: int | None
    details: str | None
    ip_address: str | None


def list_audit(session: Session, filters: ListFilters, action: str = "", entity: str = "") -> Page[AuditEntry]:
    statement = select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id)
    conditions = date_conditions(filters, AuditLog.occurred_at)
    if action:
        conditions.append(AuditLog.action == action)
    if entity:
        conditions.append(AuditLog.entity == entity)
    if conditions:
        statement = statement.where(and_(*conditions))
    statement = statement.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = session.execute(statement.limit(filters.limit).offset(filters.offset)).all()
    entries = [
        AuditEntry(log.id, log.occurred_at, username, log.action, log.entity, log.entity_id, log.details, log.ip_address)
        for log, username in rows
    ]
    return Page(entries, total)


@dataclass(frozen=True)
class DeletionImpact:
    documents: int
    images: int


def person_deletion_impact(person: Person) -> DeletionImpact:
    return DeletionImpact(len(person.documents), sum(len(document.images) for document in person.documents))


def document_deletion_impact(document: Document) -> DeletionImpact:
    return DeletionImpact(1, len(document.images))

