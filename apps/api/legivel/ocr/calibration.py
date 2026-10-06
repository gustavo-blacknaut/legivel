from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
)
LINES = (
    ("REGISTRO GERAL", 22),
    ("12.345.678-9", 34),
    ("NOME", 22),
    ("MARIA FICTICIA DE SOUZA", 34),
    ("FILIACAO", 22),
    ("JOAO FICTICIO DE SOUZA", 34),
    ("ANA FICTICIA DE SOUZA", 34),
    ("NATURALIDADE", 22),
    ("SAO PAULO-SP", 34),
    ("DATA DE NASCIMENTO", 22),
    ("01/02/1990", 34),
)


def font(size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


@lru_cache
def calibration_document() -> np.ndarray:
    page = Image.new("RGB", (1400, 960), (226, 236, 226))
    draw = ImageDraw.Draw(page)
    y = 40
    for text, size in LINES:
        draw.text((50, y), text, fill=(25, 30, 28), font=font(size))
        y += size + (10 if size < 30 else 26)
    return cv2.cvtColor(np.asarray(page), cv2.COLOR_RGB2BGR)
