from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from legivel.db.base import Base, utc_now
from legivel.security.fields import EncryptedJSON, EncryptedText, blind_index


class DocumentType(StrEnum):
    RG = "rg"
    CNH = "cnh"
    CPF = "cpf"


class DocumentStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"


class ImageSide(StrEnum):
    FRONT = "front"
    BACK = "back"
    OPEN = "open"


class ImageKind(StrEnum):
    PAGE = "page"
    PORTRAIT = "portrait"
    FINGERPRINT = "fingerprint"
    SIGNATURE = "signature"


class UserRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    READER = "reader"


class TokenPurpose(StrEnum):
    INVITE = "invite"
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.READER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pending_email: Mapped[str | None] = mapped_column(String(254))
    totp_secret: Mapped[str | None] = mapped_column(String(255))
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_codes: Mapped[list | None] = mapped_column(JSON, default=list)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def display_name(self) -> str:
        return self.name or self.email

    @property
    def two_factor_enabled(self) -> bool:
        return self.totp_enabled_at is not None


class UserToken(Base):
    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    role: Mapped[str | None] = mapped_column(String(16))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cpf: Mapped[str | None] = mapped_column(EncryptedText)
    cpf_index: Mapped[str | None] = mapped_column(String(64), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(200), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    mother_name: Mapped[str | None] = mapped_column(String(200))
    father_name: Mapped[str | None] = mapped_column(String(200))
    birthplace: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    documents: Mapped[list["Document"]] = relationship(back_populates="person", cascade="all, delete-orphan")

    @validates("cpf")
    def index_cpf(self, _key: str, value: str | None) -> str | None:
        self.cpf_index = blind_index(value)
        return value


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.PENDING_REVIEW, index=True)
    reviewed_manually: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_engine: Mapped[str | None] = mapped_column(String(32))
    ocr_confidence_avg: Mapped[float | None] = mapped_column(Float)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    full_name: Mapped[str | None] = mapped_column(String(200))
    cpf: Mapped[str | None] = mapped_column(EncryptedText)
    cpf_index: Mapped[str | None] = mapped_column(String(64), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    mother_name: Mapped[str | None] = mapped_column(String(200))
    father_name: Mapped[str | None] = mapped_column(String(200))
    birthplace: Mapped[str | None] = mapped_column(String(120))
    rg_number: Mapped[str | None] = mapped_column(EncryptedText)
    issuing_authority: Mapped[str | None] = mapped_column(String(32))
    issue_date: Mapped[date | None] = mapped_column(Date)
    cnh_register: Mapped[str | None] = mapped_column(EncryptedText)
    cnh_category: Mapped[str | None] = mapped_column(String(8))
    valid_until: Mapped[date | None] = mapped_column(Date)
    first_license_date: Mapped[date | None] = mapped_column(Date)
    mrz_raw: Mapped[str | None] = mapped_column(EncryptedText)

    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    extra_fields: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    raw_text: Mapped[str | None] = mapped_column(EncryptedText)

    person: Mapped[Person | None] = relationship(back_populates="documents")
    images: Mapped[list["DocumentImage"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    @validates("cpf")
    def index_cpf(self, _key: str, value: str | None) -> str | None:
        self.cpf_index = blind_index(value)
        return value


class DocumentImage(Base):
    __tablename__ = "document_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    side: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(16), default=ImageKind.PAGE, server_default=ImageKind.PAGE.value)
    original_path: Mapped[str] = mapped_column(String(255))
    processed_path: Mapped[str | None] = mapped_column(String(255))
    thumbnail_path: Mapped[str | None] = mapped_column(String(255))
    original_mime: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[Document] = relationship(back_populates="images")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32), index=True)
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    details: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScanLink(Base):
    __tablename__ = "scan_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.PENDING_REVIEW, index=True)
    language: Mapped[str | None] = mapped_column(String(8))
    confidence: Mapped[float | None] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    search_text: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    pages: Mapped[list["RecordPage"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="RecordPage.page_number"
    )
    card: Mapped["CardDetail | None"] = relationship(back_populates="record", cascade="all, delete-orphan", uselist=False)


class RecordPage(Base):
    __tablename__ = "record_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    original_path: Mapped[str | None] = mapped_column(String(255))
    processed_path: Mapped[str | None] = mapped_column(String(255))
    thumbnail_path: Mapped[str | None] = mapped_column(String(255))
    original_mime: Mapped[str | None] = mapped_column(String(64))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(EncryptedText)
    layout: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)

    record: Mapped[Record] = relationship(back_populates="pages")


class CardDetail(Base):
    __tablename__ = "card_details"

    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), primary_key=True)
    brand: Mapped[str | None] = mapped_column(String(32))
    last4: Mapped[str | None] = mapped_column(String(4))
    holder_name: Mapped[str | None] = mapped_column(EncryptedText)
    expiry: Mapped[str | None] = mapped_column(String(5))
    luhn_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    full_number: Mapped[str | None] = mapped_column(EncryptedText)

    record: Mapped[Record] = relationship(back_populates="card")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    payload: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    completed_pages: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer)
    result_id: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class OrganizationEntry(Base):
    __tablename__ = "organization_entries"
    __table_args__ = (UniqueConstraint("user_id", "entity", "entity_id", name="uq_organization_owner_entity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entity: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[int] = mapped_column(Integer)
    folder: Mapped[str] = mapped_column(String(100), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    path: Mapped[str] = mapped_column(String(2000))
