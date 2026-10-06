"""indexes for filtered and paginated lists

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_people_created_at", "people", ["created_at"])
    op.create_index("ix_documents_processed_at", "documents", ["processed_at"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_action", "audit_log")
    op.drop_index("ix_documents_status", "documents")
    op.drop_index("ix_documents_processed_at", "documents")
    op.drop_index("ix_people_created_at", "people")
