"""image kind for document crops

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("document_images") as batch:
        batch.add_column(sa.Column("kind", sa.String(16), nullable=False, server_default="page"))


def downgrade() -> None:
    with op.batch_alter_table("document_images") as batch:
        batch.drop_column("kind")
