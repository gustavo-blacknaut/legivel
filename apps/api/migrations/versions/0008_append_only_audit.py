"""append-only audit log

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-05
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

MESSAGE = "audit_log is append-only"
UNCHANGED_EXCEPT_USER = (
    "NEW.id = OLD.id AND NEW.action = OLD.action AND NEW.entity = OLD.entity"
    " AND NEW.entity_id IS NOT DISTINCT FROM OLD.entity_id AND NEW.occurred_at = OLD.occurred_at"
    " AND NEW.details IS NOT DISTINCT FROM OLD.details AND NEW.ip_address IS NOT DISTINCT FROM OLD.ip_address"
)
POSTGRES_FUNCTION = f"""
CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND {UNCHANGED_EXCEPT_USER} THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '{MESSAGE}';
END;
$$ LANGUAGE plpgsql
"""
SQLITE_UNCHANGED_EXCEPT_USER = UNCHANGED_EXCEPT_USER.replace("IS NOT DISTINCT FROM", "IS")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POSTGRES_FUNCTION)
        op.execute(
            "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log"
            " FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()"
        )
        op.execute(
            "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log"
            " FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only()"
        )
        return
    op.execute(f"CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, '{MESSAGE}'); END")
    op.execute(
        "CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log"
        f" WHEN NOT (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND {SQLITE_UNCHANGED_EXCEPT_USER})"
        f" BEGIN SELECT RAISE(ABORT, '{MESSAGE}'); END"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER audit_log_no_truncate ON audit_log")
        op.execute("DROP TRIGGER audit_log_append_only ON audit_log")
        op.execute("DROP FUNCTION audit_log_append_only()")
        return
    op.execute("DROP TRIGGER audit_log_no_update")
    op.execute("DROP TRIGGER audit_log_no_delete")
