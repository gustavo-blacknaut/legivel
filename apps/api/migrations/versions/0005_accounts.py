"""e-mail accounts, roles, two-factor and one-time tokens

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

LOCAL_DOMAIN = "@legivel.local"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email", sa.String(254), nullable=True))
        batch.add_column(sa.Column("name", sa.String(120), nullable=False, server_default=""))
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("pending_email", sa.String(254), nullable=True))
        batch.add_column(sa.Column("totp_secret", sa.String(255), nullable=True))
        batch.add_column(sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("recovery_codes", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    users = sa.table("users", sa.column("id"), sa.column("username"), sa.column("email"), sa.column("name"), sa.column("role"))
    connection = op.get_bind()
    for user_id, username, role in connection.execute(sa.select(users.c.id, users.c.username, users.c.role)).all():
        email = username.lower() if "@" in username else f"{username.lower()}{LOCAL_DOMAIN}"
        connection.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(email=email, name=username, role="reviewer" if role == "operator" else role)
        )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(254), nullable=False)
        batch.drop_constraint("uq_users_username", type_="unique")
        batch.drop_column("username")
        batch.create_unique_constraint("uq_users_email", ["email"])
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_tokens_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_user_tokens_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_user_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_user_tokens_token_hash"),
    )
    op.create_index("ix_user_tokens_purpose", "user_tokens", ["purpose"])
    op.create_index("ix_user_tokens_email", "user_tokens", ["email"])
    op.create_index("ix_user_tokens_user_id", "user_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_tokens_user_id", table_name="user_tokens")
    op.drop_index("ix_user_tokens_email", table_name="user_tokens")
    op.drop_index("ix_user_tokens_purpose", table_name="user_tokens")
    op.drop_table("user_tokens")
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username", sa.String(64), nullable=True))
    users = sa.table("users", sa.column("id"), sa.column("username"), sa.column("email"), sa.column("role"))
    connection = op.get_bind()
    for user_id, email, role in connection.execute(sa.select(users.c.id, users.c.email, users.c.role)).all():
        connection.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(username=email.removesuffix(LOCAL_DOMAIN)[:64], role="operator" if role != "admin" else role)
        )
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_email", type_="unique")
        batch.alter_column("username", existing_type=sa.String(64), nullable=False)
        batch.create_unique_constraint("uq_users_username", ["username"])
        for column in (
            "last_login_at", "password_changed_at", "locked_until", "failed_logins", "recovery_codes", "totp_enabled_at",
            "totp_secret", "pending_email", "email_verified_at", "name", "email",
        ):
            batch.drop_column(column)
