import argparse
from pathlib import Path

from PIL import Image

WIDTH = 960
FRAME_MS = 1400


def main() -> None:
    parser = argparse.ArgumentParser(description="Monta o GIF do fluxo principal a partir das capturas do Playwright")
    parser.add_argument("--frames", default="docs/screenshots/frames")
    parser.add_argument("--output", default="docs/screenshots/fluxo.gif")
    arguments = parser.parse_args()
    paths = sorted(Path(arguments.frames).glob("*.png"))
    if not paths:
        raise SystemExit("Nenhum quadro encontrado. Rode SCREENSHOTS=1 npx playwright test --project=screenshots antes.")
    frames = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        height = round(image.height * WIDTH / image.width)
        frames.append(image.resize((WIDTH, height), Image.LANCZOS).quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    frames[0].save(arguments.output, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0, optimize=True)
    print(f"{len(frames)} quadros em {arguments.output}")


if __name__ == "__main__":
    main()
