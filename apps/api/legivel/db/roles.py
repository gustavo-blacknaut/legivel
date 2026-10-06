import re

from psycopg import sql
from sqlalchemy import Engine

ROLE_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
READ_ONLY_TABLES = ("alembic_version",)
APPEND_ONLY_TABLES = ("audit_log",)


class RoleError(ValueError):
    pass


def role_statements(role: str, password: str, database: str) -> list[sql.Composable]:
    name = sql.Identifier(role)
    statements = [
        sql.SQL(
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = {role_literal}) "
            "THEN CREATE ROLE {name} LOGIN; END IF; END $$"
        ).format(role_literal=sql.Literal(role), name=name),
        sql.SQL("ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}").format(
            name, sql.Literal(password)
        ),
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), name),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(name),
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(name),
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(name),
    ]
    for table in READ_ONLY_TABLES:
        statements.append(sql.SQL("REVOKE INSERT, UPDATE, DELETE ON {} FROM {}").format(sql.Identifier(table), name))
    for table in APPEND_ONLY_TABLES:
        statements.append(sql.SQL("REVOKE UPDATE, DELETE ON {} FROM {}").format(sql.Identifier(table), name))
    return statements


def grant_application_role(engine: Engine, role: str, password: str) -> None:
    if engine.dialect.name != "postgresql":
        raise RoleError("O usuário da aplicação só existe no PostgreSQL.")
    if not ROLE_NAME_PATTERN.match(role):
        raise RoleError("Nome de usuário inválido: use letras minúsculas, números e _.")
    if len(password) < 16:
        raise RoleError("A senha do usuário da aplicação precisa ter pelo menos 16 caracteres.")
    with engine.begin() as connection:
        if connection.exec_driver_sql("SELECT current_user").scalar() == role:
            raise RoleError("Rode este comando com o dono do banco, não com o usuário da aplicação.")
        database = connection.exec_driver_sql("SELECT current_database()").scalar()
        driver_connection = connection.connection.driver_connection
        for statement in role_statements(role, password, database):
            driver_connection.execute(statement)
