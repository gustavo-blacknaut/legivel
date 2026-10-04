"""generic records for OCR modules

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("field_confidence", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_records_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_records"),
    )
    op.create_index("ix_records_module", "records", ["module"])
    op.create_index("ix_records_status", "records", ["status"])
    op.create_index("ix_records_created_at", "records", ["created_at"])
    op.create_table(
        "record_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("original_path", sa.String(255), nullable=True),
        sa.Column("processed_path", sa.String(255), nullable=True),
        sa.Column("thumbnail_path", sa.String(255), nullable=True),
        sa.Column("original_mime", sa.String(64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("layout", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"], name="fk_record_pages_record_id_records", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_record_pages"),
    )
    op.create_index("ix_record_pages_record_id", "record_pages", ["record_id"])
    op.create_table(
        "card_details",
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(32), nullable=True),
        sa.Column("last4", sa.String(4), nullable=True),
        sa.Column("holder_name", sa.String(120), nullable=True),
        sa.Column("expiry", sa.String(5), nullable=True),
        sa.Column("luhn_valid", sa.Boolean(), nullable=False),
        sa.Column("encrypted_number", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"], name="fk_card_details_record_id_records", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id", name="pk_card_details"),
    )


def downgrade() -> None:
    op.drop_table("card_details")
    op.drop_table("record_pages")
    op.drop_table("records")
