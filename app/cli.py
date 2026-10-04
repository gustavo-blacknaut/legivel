import argparse
import getpass
import secrets
from pathlib import Path

from app.auth.users import create_user
from app.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.security.crypto import generate_key

GENERATED_PASSWORD_BYTES = 12


def read_password(arguments: argparse.Namespace) -> str:
    if arguments.generate:
        return secrets.token_urlsafe(GENERATED_PASSWORD_BYTES)
    password = getpass.getpass("Senha: ")
    if password != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem")
    return password


def run_create_user(arguments: argparse.Namespace) -> None:
    password = read_password(arguments)
    factory = build_session_factory(build_engine(get_settings().database_url))
    with factory() as session:
        try:
            create_user(session, arguments.username, password)
        except ValueError as error:
            raise SystemExit(str(error)) from error
    if arguments.generate:
        output = Path(arguments.output)
        output.write_text(f"usuario: {arguments.username}\nsenha: {password}\n", encoding="utf-8")
        output.chmod(0o600)
        print(f"Usuário '{arguments.username}' criado. Senha gravada em {output}")
    else:
        print(f"Usuário '{arguments.username}' salvo")


def main() -> None:
    parser = argparse.ArgumentParser(prog="registra")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate-key", help="Gera uma chave para GREEN_OCR_ENCRYPTION_KEY ou GREEN_OCR_SECRET_KEY")
    user_parser = commands.add_parser("create-user", help="Cria um usuário ou redefine a senha de um existente")
    user_parser.add_argument("username")
    user_parser.add_argument("--generate", action="store_true", help="Gera uma senha aleatória e grava em arquivo")
    user_parser.add_argument("--output", default="data/credenciais.txt")
    arguments = parser.parse_args()
    if arguments.command == "generate-key":
        print(generate_key())
    elif arguments.command == "create-user":
        run_create_user(arguments)


if __name__ == "__main__":
    main()
