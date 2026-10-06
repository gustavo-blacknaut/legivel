import re
from pathlib import Path

import pytest

from legivel.config import ENV_PREFIX, Settings

PARENTS = Path(__file__).resolve().parents
ROOT = PARENTS[3] if len(PARENTS) > 3 else PARENTS[-1]
EXAMPLE = ROOT / ".env.example"
GUIDE = ROOT / "docs" / "configuracao.md"
COMPOSE_ONLY = {
    "LEGIVEL_BIND",
    "LEGIVEL_PORT",
    "LEGIVEL_API_URL",
    "LEGIVEL_STORAGE_PATH",
    "LEGIVEL_API_MEMORY_LIMIT",
    "LEGIVEL_WEB_MEMORY_LIMIT",
}


def documented(path: Path) -> set[str]:
    return set(re.findall(rf"^({ENV_PREFIX}[A-Z0-9_]+)=", path.read_text(encoding="utf-8"), re.MULTILINE))


@pytest.mark.skipif(not EXAMPLE.exists(), reason=".env.example fica na raiz do repositório")
def test_env_example_lists_every_setting():
    variables = documented(EXAMPLE) - COMPOSE_ONLY
    fields = {f"{ENV_PREFIX}{name.upper()}" for name in Settings.model_fields}
    assert variables == fields


@pytest.mark.skipif(not GUIDE.exists(), reason="docs/configuracao.md fica na raiz do repositório")
def test_configuration_guide_mentions_every_setting():
    text = GUIDE.read_text(encoding="utf-8")
    missing = [f"{ENV_PREFIX}{name.upper()}" for name in Settings.model_fields if f"{ENV_PREFIX}{name.upper()}" not in text]
    assert missing == []
