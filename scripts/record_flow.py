import argparse
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

FRAME_SIZE = (1280, 800)
OUTPUT_WIDTH = 960


class Recorder:
    def __init__(self, page: Page):
        self.page = page
        self.frames: list[tuple[Image.Image, int]] = []

    def hold(self, milliseconds: int) -> None:
        image = Image.open(io.BytesIO(self.page.screenshot())).convert("RGB")
        height = round(image.height * OUTPUT_WIDTH / image.width)
        self.frames.append((image.resize((OUTPUT_WIDTH, height), Image.LANCZOS), milliseconds))

    def save(self, path: Path) -> None:
        palette_frames = [frame.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for frame, _ in self.frames]
        palette_frames[0].save(
            path,
            save_all=True,
            append_images=palette_frames[1:],
            duration=[duration for _, duration in self.frames],
            loop=0,
            optimize=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", default="docs/screenshots/fluxo.gif")
    arguments = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": FRAME_SIZE[0], "height": FRAME_SIZE[1]}, color_scheme="light")
        recorder = Recorder(page)
        page.goto(f"{arguments.base_url}/pessoas")
        page.fill("#username", arguments.username)
        page.fill("#password", arguments.password)
        page.click("button[type=submit]")
        page.wait_for_selector(".table tbody tr")
        page.wait_for_timeout(500)
        recorder.hold(1600)
        page.click("text=Novo documento >> nth=0")
        page.wait_for_selector(".dropzone")
        recorder.hold(1000)
        page.set_input_files(".dropzone >> nth=1 >> input", arguments.image)
        page.wait_for_timeout(400)
        recorder.hold(1200)
        page.click("button:has-text('Extrair dados')")
        page.wait_for_timeout(250)
        recorder.hold(1400)
        page.wait_for_selector(".form-section", timeout=120_000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        recorder.hold(2600)
        page.click("button:has-text('Confirmar revisão')")
        page.wait_for_timeout(600)
        recorder.hold(1800)
        page.click("text=Voltar para a pessoa")
        page.wait_for_selector(".meta-list")
        page.wait_for_timeout(400)
        recorder.hold(2200)
        recorder.save(Path(arguments.output))
        browser.close()


if __name__ == "__main__":
    main()
