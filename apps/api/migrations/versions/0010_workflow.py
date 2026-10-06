"""Persistent processing and personal organization."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("completed_pages", sa.Integer(), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("result_id", sa.Integer()),
        sa.Column("error", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_processing_jobs_user_id", "processing_jobs", ["user_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_table(
        "organization_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("folder", sa.String(100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.UniqueConstraint("user_id", "entity", "entity_id", name="uq_organization_owner_entity"),
    )
    op.create_index("ix_organization_entries_user_id", "organization_entries", ["user_id"])
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("path", sa.String(2000), nullable=False),
    )
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])


def downgrade() -> None:
    op.drop_table("saved_searches")
    op.drop_table("organization_entries")
    op.drop_table("processing_jobs")
