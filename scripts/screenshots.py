import argparse
import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WIDTHS = (360, 768, 1280, 1920)
HEIGHTS = {360: 780, 768: 1024, 1280: 800, 1920: 1080}
MOBILE_BREAKPOINT = 860


def login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/busca")
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type=submit]")
    page.wait_for_selector(".sidebar")


def settle(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)


def capture(page: Page, output: Path, name: str, width: int, theme: str, full_page: bool = False) -> None:
    page.screenshot(path=str(output / f"{name}-{width}-{theme}.png"), full_page=full_page)
    print(f"{name}-{width}-{theme}.png")


def record_id(page: Page, base_url: str, module: str) -> int:
    response = page.request.get(f"{base_url}/api/records?module={module}&page_size=1")
    return json.loads(response.text())["items"][0]["id"]


def capture_width(page: Page, base_url: str, output: Path, width: int, theme: str) -> None:
    mobile = width < MOBILE_BREAKPOINT
    page.goto(f"{base_url}/busca")
    page.wait_for_selector(".result-list li")
    settle(page)
    capture(page, output, "busca", width, theme)

    if mobile:
        page.click("button[aria-label='Abrir menu']")
        page.wait_for_timeout(350)
        capture(page, output, "sidebar-aberta", width, theme)
        page.keyboard.press("Escape")
        page.wait_for_timeout(350)
    else:
        capture(page, output, "sidebar-aberta", width, theme)
        page.click("button[aria-label='Recolher menu']")
        page.wait_for_timeout(300)
        capture(page, output, "sidebar-fechada", width, theme)
        page.click("button[aria-label='Expandir menu']")
        page.wait_for_timeout(300)

    for module in ("books", "scanner", "finance", "cards"):
        page.goto(f"{base_url}/modulos/{module}")
        page.wait_for_selector(".page-picker")
        settle(page)
        capture(page, output, f"modulo-{module}", width, theme)
        page.goto(f"{base_url}/registros/{record_id(page, base_url, module)}")
        page.wait_for_selector(".form-grid")
        settle(page)
        capture(page, output, f"registro-{module}", width, theme, full_page=True)

    page.click("text=Apagar registro")
    page.wait_for_selector(".dialog")
    page.wait_for_timeout(300)
    capture(page, output, "modal-apagar", width, theme)
    page.keyboard.press("Escape")

    page.goto(f"{base_url}/configuracoes")
    page.wait_for_selector(".settings-checks")
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
        browser = playwright.chromium.launch()
        for theme in arguments.themes.split(","):
            for width in WIDTHS:
                context = browser.new_context(
                    viewport={"width": width, "height": HEIGHTS[width]}, color_scheme=theme, locale="pt-BR"
                )
                page = context.new_page()
                login(page, arguments.base_url, arguments.username, arguments.password)
                capture_width(page, arguments.base_url, output, width, theme)
                context.close()
        browser.close()


if __name__ == "__main__":
    main()
