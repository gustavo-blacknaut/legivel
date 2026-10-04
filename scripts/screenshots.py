import argparse
import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WIDTHS = (360, 768, 1280, 1920)
HEIGHTS = {360: 780, 768: 1024, 1280: 800, 1920: 1080}
MOBILE_BREAKPOINT = 860


def login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/pessoas")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type=submit]")
    page.wait_for_selector(".sidebar")


def settle(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)


def newest_document_id(page: Page, base_url: str) -> int:
    response = page.request.get(f"{base_url}/api/documents?page_size=1")
    return json.loads(response.text())["items"][0]["id"]


def newest_person_id(page: Page, base_url: str) -> int:
    response = page.request.get(f"{base_url}/api/people?page_size=1")
    return json.loads(response.text())["items"][0]["id"]


def capture(page: Page, output: Path, name: str, width: int, theme: str, full_page: bool = False) -> None:
    path = output / f"{name}-{width}-{theme}.png"
    page.screenshot(path=str(path), full_page=full_page)
    print(path.name)


def capture_width(page: Page, base_url: str, output: Path, width: int, theme: str) -> None:
    mobile = width < MOBILE_BREAKPOINT
    page.goto(f"{base_url}/pessoas")
    page.wait_for_selector(".table tbody tr")
    settle(page)
    capture(page, output, "pessoas", width, theme)

    if width < 720:
        page.click(".filters-toggle")
        page.wait_for_timeout(200)
        capture(page, output, "pessoas-filtros", width, theme)
        page.click(".filters-toggle")

    if mobile:
        page.click("button[aria-label='Abrir menu']")
        page.wait_for_timeout(350)
        capture(page, output, "sidebar-aberta", width, theme)
        page.keyboard.press("Escape")
        page.wait_for_timeout(350)
        capture(page, output, "sidebar-fechada", width, theme)
    else:
        capture(page, output, "sidebar-aberta", width, theme)
        page.click("button[aria-label='Recolher menu']")
        page.wait_for_timeout(300)
        capture(page, output, "sidebar-fechada", width, theme)
        page.click("button[aria-label='Expandir menu']")
        page.wait_for_timeout(300)

    page.goto(f"{base_url}/pessoas?status=pending_review&sort=name&order=asc")
    page.wait_for_selector(".table tbody tr")
    settle(page)
    capture(page, output, "pessoas-filtradas", width, theme)

    page.locator(".table tbody tr").first.locator("button[aria-label^='Apagar']").click()
    page.wait_for_selector(".dialog")
    page.wait_for_timeout(300)
    capture(page, output, "modal-apagar-pessoa", width, theme)
    page.keyboard.press("Escape")

    page.goto(f"{base_url}/documentos/{newest_document_id(page, base_url)}")
    page.wait_for_selector(".form-section")
    settle(page)
    capture(page, output, "revisao", width, theme)
    capture(page, output, "revisao-completa", width, theme, full_page=True)
    page.click("text=Apagar documento")
    page.wait_for_selector(".dialog")
    page.wait_for_timeout(300)
    capture(page, output, "modal-apagar-documento", width, theme)
    page.keyboard.press("Escape")

    page.goto(f"{base_url}/novo")
    settle(page)
    capture(page, output, "novo-documento", width, theme)
    page.click("button:has-text('Gerar link de envio')")
    page.fill("input[placeholder^='Ex.']", "Admissão — vaga de recepção")
    page.click("button:has-text('Gerar')")
    page.wait_for_selector(".link-result")
    public_url = page.locator(".link-box input").input_value()
    capture(page, output, "link-envio", width, theme, full_page=True)

    visitor = page.context.browser.new_context(viewport=page.viewport_size, color_scheme=theme)
    public_page = visitor.new_page()
    public_page.goto(f"{base_url}/enviar/{public_url.split('/enviar/')[1]}")
    public_page.wait_for_selector(".dropzone")
    capture(public_page, output, "envio-publico", width, theme)
    visitor.close()

    page.goto(f"{base_url}/pessoas/{newest_person_id(page, base_url)}")
    page.wait_for_selector(".meta-list")
    settle(page)
    page.click("button:has-text('Verificar')")
    page.wait_for_selector(".verification")
    capture(page, output, "pessoa", width, theme, full_page=True)
    page.click("button:has-text('Editar')")
    capture(page, output, "pessoa-editar", width, theme)

    page.goto(f"{base_url}/auditoria")
    page.wait_for_selector(".audit-table tbody tr")
    settle(page)
    capture(page, output, "auditoria", width, theme)

    page.goto(f"{base_url}/configuracoes")
    page.wait_for_selector(".session-list")
    settle(page)
    capture(page, output, "configuracoes", width, theme, full_page=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", default="docs/screenshots/qa")
    parser.add_argument("--themes", default="light,dark")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--lang=pt-BR"])
        for theme in arguments.themes.split(","):
            for width in WIDTHS:
                context = browser.new_context(
                    viewport={"width": width, "height": HEIGHTS[width]},
                    device_scale_factor=1,
                    color_scheme=theme,
                    locale="pt-BR",
                    timezone_id="America/Sao_Paulo",
                )
                page = context.new_page()
                login(page, arguments.base_url, arguments.username, arguments.password)
                capture_width(page, arguments.base_url, output, width, theme)
                context.close()
        browser.close()


if __name__ == "__main__":
    main()
