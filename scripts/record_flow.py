import argparse
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

OUTPUT_WIDTH = 960


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--output", default="docs/screenshots/fluxo.gif")
    arguments = parser.parse_args()
    frames: list[tuple[Image.Image, int]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme="light")

        def hold(milliseconds: int) -> None:
            image = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            height = round(image.height * OUTPUT_WIDTH / image.width)
            frames.append((image.resize((OUTPUT_WIDTH, height), Image.LANCZOS), milliseconds))

        page.goto(f"{arguments.base_url}/busca")
        page.fill("#username", arguments.username)
        page.fill("#password", arguments.password)
        page.click("button[type=submit]")
        page.wait_for_selector(".result-list li")
        page.wait_for_timeout(400)
        hold(1500)
        page.click("text=Livros e textos")
        page.wait_for_selector(".page-picker")
        page.wait_for_timeout(300)
        hold(1100)
        page.set_input_files(".page-picker input[type=file]", arguments.images)
        page.wait_for_timeout(500)
        hold(1400)
        page.click("button:has-text('Processar')")
        page.wait_for_timeout(300)
        hold(1300)
        page.wait_for_url("**/registros/**", timeout=300_000)
        page.wait_for_selector(".page-grid")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        hold(2400)
        page.click("text=Texto reconhecido")
        page.wait_for_timeout(300)
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(300)
        hold(2400)
        page.goto(f"{arguments.base_url}/busca?q=cooperativa")
        page.wait_for_selector(".result-list li")
        page.wait_for_timeout(500)
        hold(2200)
        browser.close()
    palette = [frame.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for frame, _ in frames]
    palette[0].save(
        Path(arguments.output),
        save_all=True,
        append_images=palette[1:],
        duration=[duration for _, duration in frames],
        loop=0,
        optimize=True,
    )


if __name__ == "__main__":
    main()
