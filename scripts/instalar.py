"""Assistente de instalação local com Docker Compose."""

import argparse
import base64
import os
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = {
    "postgres_password": "POSTGRES_PASSWORD",
    "database_app_password": "",
    "secret_key": "LEGIVEL_SECRET_KEY",
    "encryption_key": "LEGIVEL_ENCRYPTION_KEY",
    "backup_passphrase": "",
}


def environment_values(path: Path) -> dict[str, str]:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                values[name.strip()] = value.strip().strip("\"'")
    return values


def prepare_files(root: Path, port: int) -> None:
    env = root / ".env"
    if not env.exists():
        text = (root / ".env.example").read_text(encoding="utf-8")
        env.write_text(
            text.replace("LEGIVEL_PORT=8091", f"LEGIVEL_PORT={port}"), encoding="utf-8"
        )
    values = environment_values(env)
    directory = root / "secrets"
    directory.mkdir(exist_ok=True)
    if os.name != "nt":
        directory.chmod(0o700)
    for name, variable in SECRET_NAMES.items():
        path = directory / name
        if path.exists() and path.stat().st_size:
            continue
        value = values.get(variable, "") if variable else ""
        if not value:
            value = (
                base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
                if name in ("secret_key", "encryption_key")
                else secrets.token_urlsafe(32)
            )
        with path.open("w", encoding="utf-8") as stream:
            if os.name != "nt":
                os.fchmod(stream.fileno(), 0o600)
            stream.write(value)
    # Existing keys and database settings are preserved on every subsequent run.


def run(*command: str, timeout: int = 60) -> None:
    result = subprocess.run(command, cwd=ROOT, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(
            f"Falha em {' '.join(command[:3])}. Confira a mensagem acima."
        )


def wait_for_web(url: str, seconds: int = 180) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(2)
    raise RuntimeError(
        "A interface não respondeu. Confira: docker compose logs api web migrate"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument(
        "--yes", action="store_true", help="Usa as opções padrão sem perguntas"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Confere Docker sem criar arquivos ou subir serviços",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Prepara arquivos e confere configuração sem subir serviços",
    )
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("A porta deve estar entre 1 e 65535")
    if shutil.which("docker") is None:
        raise SystemExit("Instale o Docker com Compose e abra-o antes de continuar.")
    try:
        run("docker", "compose", "version")
        run("docker", "info", "--format", "{{.ServerVersion}}")
        if arguments.check_only:
            print("Docker e Compose disponíveis. Nenhum arquivo foi alterado.")
            return
        port = arguments.port
        if not arguments.yes and not (ROOT / ".env").exists():
            answer = input(f"Porta da interface [{port}]: ").strip()
            if answer:
                port = int(answer)
                if not 1 <= port <= 65535:
                    raise ValueError("Porta inválida")
        prepare_files(ROOT, port)
        run("docker", "compose", "config", "--quiet")
        if arguments.no_start:
            print("Configuração preparada. Para iniciar: docker compose up -d --build")
            return
        print("Construindo e iniciando o Legível. O primeiro build pode demorar.")
        run("docker", "compose", "up", "-d", "--build", timeout=1800)
        values = environment_values(ROOT / ".env")
        bind = values.get("LEGIVEL_BIND", "127.0.0.1")
        host = "127.0.0.1" if bind == "0.0.0.0" else bind
        url = f"http://{host}:{values.get('LEGIVEL_PORT', str(port))}"
        wait_for_web(url)
        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "legivel.cli",
            "check-config",
        )
        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            "from legivel.config import get_settings; from legivel.db.session import build_engine; "
            "from sqlalchemy import text; engine=build_engine(get_settings().database_url); "
            "connection=engine.connect(); connection.execute(text('SELECT 1')); connection.close(); print('Banco: OK')",
        )
        run(
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "legivel.cli",
            "ocr-status",
            timeout=180,
        )
        print(f"Pronto. Abra {url} e crie o administrador.")
        print("Guarde uma cópia da pasta secrets fora do servidor.")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
