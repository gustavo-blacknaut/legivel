"""encrypted personal fields and CPF blind index

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

DOCUMENT_TEXT_COLUMNS = (("cpf", sa.String(11)), ("rg_number", sa.String(32)), ("cnh_register", sa.String(16)))


def upgrade() -> None:
    with op.batch_alter_table("people") as batch:
        batch.drop_constraint("uq_people_cpf", type_="unique")
        batch.alter_column("cpf", existing_type=sa.String(11), type_=sa.Text())
        batch.add_column(sa.Column("cpf_index", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_people_cpf_index", ["cpf_index"])
    op.drop_index("ix_documents_cpf", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        for name, previous in DOCUMENT_TEXT_COLUMNS:
            batch.alter_column(name, existing_type=previous, type_=sa.Text())
        batch.alter_column("extra_fields", existing_type=sa.JSON(), type_=sa.Text(), postgresql_using="extra_fields::text")
        batch.add_column(sa.Column("cpf_index", sa.String(64), nullable=True))
    op.create_index("ix_documents_cpf_index", "documents", ["cpf_index"])


def downgrade() -> None:
    op.drop_index("ix_documents_cpf_index", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("cpf_index")
        batch.alter_column("extra_fields", existing_type=sa.Text(), type_=sa.JSON(), postgresql_using="extra_fields::json")
        for name, previous in DOCUMENT_TEXT_COLUMNS:
            batch.alter_column(name, existing_type=sa.Text(), type_=previous)
    op.create_index("ix_documents_cpf", "documents", ["cpf"])
    with op.batch_alter_table("people") as batch:
        batch.drop_constraint("uq_people_cpf_index", type_="unique")
        batch.drop_column("cpf_index")
        batch.alter_column("cpf", existing_type=sa.Text(), type_=sa.String(11))
        batch.create_unique_constraint("uq_people_cpf", ["cpf"])
