import argparse

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    arguments = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"{arguments.base_url}/pessoas")
        page.fill("#username", arguments.username)
        page.fill("#password", arguments.password)
        page.click("button[type=submit]")
        page.wait_for_selector(".table tbody tr")
        counts = [page.locator(".table tbody tr").count()]
        for _ in range(4):
            page.locator(".list-scroll").evaluate("element => element.scrollTo(0, element.scrollHeight)")
            page.wait_for_timeout(900)
            counts.append(page.locator(".table tbody tr").count())
        print("linhas após cada rolagem:", counts)
        page.goto(f"{arguments.base_url}/pessoas?status=pending_review&doc_type=cnh&sort=name&order=asc")
        page.wait_for_selector(".list-bar strong")
        print("contador com filtros da URL:", page.locator(".list-bar strong").inner_text())
        print("tipo selecionado após recarregar:", page.locator("select").first.input_value())
        browser.close()


if __name__ == "__main__":
    main()
