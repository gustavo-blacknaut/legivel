"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("mother_name", sa.String(200), nullable=True),
        sa.Column("father_name", sa.String(200), nullable=True),
        sa.Column("birthplace", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_people"),
        sa.UniqueConstraint("cpf", name="uq_people_cpf"),
    )
    op.create_index("ix_people_full_name", "people", ["full_name"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reviewed_manually", sa.Boolean(), nullable=False),
        sa.Column("ocr_engine", sa.String(32), nullable=True),
        sa.Column("ocr_confidence_avg", sa.Float(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("cpf", sa.String(11), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("mother_name", sa.String(200), nullable=True),
        sa.Column("father_name", sa.String(200), nullable=True),
        sa.Column("birthplace", sa.String(120), nullable=True),
        sa.Column("rg_number", sa.String(32), nullable=True),
        sa.Column("issuing_authority", sa.String(32), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("cnh_register", sa.String(16), nullable=True),
        sa.Column("cnh_category", sa.String(8), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("first_license_date", sa.Date(), nullable=True),
        sa.Column("mrz_raw", sa.Text(), nullable=True),
        sa.Column("field_confidence", sa.JSON(), nullable=False),
        sa.Column("extra_fields", sa.JSON(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], name="fk_documents_person_id_people", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_documents_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
    )
    op.create_index("ix_documents_person_id", "documents", ["person_id"])
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])
    op.create_index("ix_documents_cpf", "documents", ["cpf"])
    op.create_table(
        "document_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("original_path", sa.String(255), nullable=False),
        sa.Column("processed_path", sa.String(255), nullable=True),
        sa.Column("thumbnail_path", sa.String(255), nullable=True),
        sa.Column("original_mime", sa.String(64), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_document_images_document_id_documents", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_images"),
    )
    op.create_index("ix_document_images_document_id", "document_images", ["document_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("entity", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_log_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("document_images")
    op.drop_table("documents")
    op.drop_table("people")
    op.drop_table("users")
