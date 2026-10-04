import argparse
import json

import httpx

from tests.test_modules_ocr import render_bank_slip, render_card, render_english, render_two_columns
from tests.test_validators_lince import build_bank_line


def main() -> None:
    parser = argparse.ArgumentParser(description="Envia exemplos fictícios para cada módulo de uma instância de demonstração")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    arguments = parser.parse_args()
    client = httpx.Client(base_url=arguments.base_url, headers={"X-Requested-With": "lince"}, timeout=900)
    client.post("/api/auth/login", json={"username": arguments.username, "password": arguments.password}).raise_for_status()
    samples = [
        ("books", [render_two_columns(), render_english()], {}),
        ("finance", [render_bank_slip(build_bank_line("001", 9999, 25990, "0" * 6 + "1234567890123456789"))], {}),
        ("cards", [render_card()], {}),
        ("scanner", [render_two_columns(), render_english()], {"mode": "bw"}),
    ]
    for module, images, options in samples:
        files = [("pages", (f"pagina-{index}.jpg", image, "image/jpeg")) for index, image in enumerate(images)]
        response = client.post("/api/records", data={"module": module, "options": json.dumps(options)}, files=files)
        response.raise_for_status()
        print(module, response.json()["id"])


if __name__ == "__main__":
    main()
