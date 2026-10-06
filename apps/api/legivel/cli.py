import argparse
import getpass
import json
import secrets
from pathlib import Path

from legivel.config import OcrSettings, get_settings
from legivel.security.crypto import generate_key

GENERATED_PASSWORD_BYTES = 12


def read_password(arguments: argparse.Namespace) -> str:
    if arguments.generate:
        return secrets.token_urlsafe(GENERATED_PASSWORD_BYTES) + "-1"
    password = getpass.getpass("Senha: ")
    if password != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem")
    return password


def run_create_user(arguments: argparse.Namespace) -> None:
    from legivel.auth.accounts import create_user
    from legivel.auth.passwords import WeakPasswordError, configure_hashing
    from legivel.db.session import build_engine, build_session_factory
    from legivel.services.settings import load_runtime

    settings = get_settings()
    configure_hashing(settings.argon2_time_cost, settings.argon2_memory_kib, settings.argon2_parallelism)
    password = read_password(arguments)
    factory = build_session_factory(build_engine(settings.database_url))
    with factory() as session:
        try:
            create_user(session, arguments.email, password, load_runtime(session, settings), arguments.role, arguments.name)
        except WeakPasswordError as error:
            raise SystemExit(str(error)) from error
        session.commit()
    if arguments.generate:
        output = Path(arguments.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"e-mail: {arguments.email}\nsenha: {password}\n", encoding="utf-8")
        output.chmod(0o600)
        print(f"Conta '{arguments.email}' salva. Senha gravada em {output}")
    else:
        print(f"Conta '{arguments.email}' salva")


def run_download_models() -> None:
    from legivel.ocr.devices import DeviceChoice
    from legivel.ocr.rapid_engine import RapidOcrEngine

    model_dir = OcrSettings().ocr_model_dir
    RapidOcrEngine(DeviceChoice("cpu", None, "download"), model_dir)
    print(f"Modelos disponíveis em {model_dir}")


def run_ocr_status() -> None:
    from legivel.ocr.status import LABELS, ocr_status

    settings = OcrSettings()
    status = ocr_status(settings.ocr_engine, settings.ocr_device, settings.ocr_model_dir, settings.ocr_languages)
    for key, label in LABELS.items():
        if status.get(key) is not None:
            print(f"{label}: {status[key]}")


def run_reencrypt(arguments: argparse.Namespace) -> None:
    from legivel.db.session import build_engine, build_session_factory
    from legivel.security.fields import configure_fields
    from legivel.security.rotation import pending, reencrypt
    from legivel.storage.file_store import FileStore

    settings = get_settings()
    ring = settings.key_ring()
    configure_fields(ring, settings.secret_key)
    factory = build_session_factory(build_engine(settings.database_url))
    if arguments.if_needed:
        with factory() as session:
            if not pending(session, ring):
                print("Dados já cifrados com a chave atual.")
                return
    report = reencrypt(factory, FileStore(settings.storage_dir, ring), ring)
    print(f"Pessoas: {report.people}. Documentos: {report.documents}. Arquivos regravados: {report.files}.")


def run_prepare_database(arguments: argparse.Namespace) -> None:
    from legivel.db.roles import RoleError, grant_application_role
    from legivel.db.session import build_engine
    from legivel.db.transfer import upgrade

    settings = get_settings()
    upgrade(settings.database_url)
    print("Migrações aplicadas.")
    if arguments.app_user:
        password = Path(arguments.app_password_file).read_text(encoding="utf-8").strip()
        try:
            grant_application_role(build_engine(settings.database_url), arguments.app_user, password)
        except RoleError as error:
            raise SystemExit(str(error)) from error
        print(f"Permissões do usuário '{arguments.app_user}' atualizadas.")
    arguments.if_needed = True
    run_reencrypt(arguments)


def run_check_config() -> None:
    settings = get_settings()
    database = "SQLite" if settings.is_sqlite else "PostgreSQL"
    print(f"Configuração válida. Banco: {database}. SMTP: {'configurado' if settings.smtp_configured else 'não configurado'}.")


def run_export_openapi(arguments: argparse.Namespace) -> None:
    from legivel.main import openapi_document

    content = json.dumps(openapi_document(), ensure_ascii=False, indent=2) + "\n"
    if arguments.output == "-":
        print(content, end="")
        return
    Path(arguments.output).write_text(content, encoding="utf-8", newline="\n")
    print(f"OpenAPI gravado em {arguments.output}")


def run_sqlite_to_postgres(arguments: argparse.Namespace) -> None:
    from legivel.db.transfer import TransferError, copy_database

    try:
        counts = copy_database(arguments.source, arguments.target)
    except TransferError as error:
        raise SystemExit(str(error)) from error
    for item in counts:
        print(f"{item.table}: {item.copied}")
    print("Cópia concluída. Aponte LEGIVEL_DATABASE_URL para o PostgreSQL e mantenha o diretório de armazenamento.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="legivel")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate-key", help="Gera uma chave para LEGIVEL_ENCRYPTION_KEY ou LEGIVEL_SECRET_KEY")
    user_parser = commands.add_parser("create-user", help="Cria uma conta ou redefine a senha de uma existente")
    user_parser.add_argument("email")
    user_parser.add_argument("--name", default="")
    user_parser.add_argument("--role", choices=("admin", "reviewer", "reader"), default="admin")
    user_parser.add_argument("--generate", action="store_true", help="Gera uma senha aleatória e grava em arquivo")
    user_parser.add_argument("--output", default="data/credenciais.txt")
    commands.add_parser("download-models", help="Baixa os modelos de OCR para o diretório configurado")
    commands.add_parser("ocr-status", help="Mostra o dispositivo de OCR escolhido, os providers e o adaptador de vídeo")
    commands.add_parser("check-config", help="Valida as variáveis de ambiente")
    openapi_parser = commands.add_parser("export-openapi", help="Grava o esquema OpenAPI da API")
    openapi_parser.add_argument("--output", default="-")
    transfer_parser = commands.add_parser("sqlite-to-postgres", help="Copia todos os dados de um SQLite para um PostgreSQL vazio")
    transfer_parser.add_argument("--source", required=True, help="sqlite:///caminho/legivel.db")
    transfer_parser.add_argument("--target", required=True, help="postgresql://usuario:senha@host:5432/banco")
    reencrypt_parser = commands.add_parser("reencrypt", help="Cifra de novo dados e imagens com a chave atual")
    reencrypt_parser.add_argument("--if-needed", action="store_true", help="Só roda se houver dado em claro ou com chave antiga")
    prepare_parser = commands.add_parser(
        "prepare-database", help="Aplica as migrações e cria o usuário sem privilégios usado pela API"
    )
    prepare_parser.add_argument("--app-user", default="", help="Usuário do PostgreSQL usado pela API")
    prepare_parser.add_argument("--app-password-file", default="", help="Arquivo com a senha desse usuário")
    arguments = parser.parse_args()
    if arguments.command == "prepare-database" and arguments.app_user and not arguments.app_password_file:
        parser.error("--app-password-file é obrigatório com --app-user")
    if arguments.command == "generate-key":
        print(generate_key())
    elif arguments.command == "create-user":
        run_create_user(arguments)
    elif arguments.command == "download-models":
        run_download_models()
    elif arguments.command == "ocr-status":
        run_ocr_status()
    elif arguments.command == "check-config":
        run_check_config()
    elif arguments.command == "export-openapi":
        run_export_openapi(arguments)
    elif arguments.command == "reencrypt":
        run_reencrypt(arguments)
    elif arguments.command == "prepare-database":
        run_prepare_database(arguments)
    elif arguments.command == "sqlite-to-postgres":
        run_sqlite_to_postgres(arguments)


if __name__ == "__main__":
    main()
