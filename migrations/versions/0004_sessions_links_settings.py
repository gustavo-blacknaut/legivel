"""refresh tokens, scan links, settings and audit details

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log") as batch:
        batch.add_column(sa.Column("details", sa.String(255), nullable=True))
        batch.add_column(sa.Column("ip_address", sa.String(45), nullable=True))
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_app_settings"),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_table(
        "scan_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_scan_links_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_scan_links_document_id_documents", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scan_links"),
        sa.UniqueConstraint("token_hash", name="uq_scan_links_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("scan_links")
    op.drop_table("refresh_tokens")
    op.drop_table("app_settings")
    with op.batch_alter_table("audit_log") as batch:
        batch.drop_column("ip_address")
        batch.drop_column("details")
