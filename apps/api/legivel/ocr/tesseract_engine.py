import importlib.util
import shutil
import threading
import time

import cv2
import numpy as np

from legivel.ocr.base import TextBox
from legivel.ocr.devices import DeviceChoice
from legivel.ocr.rapid_engine import EngineStatistics

MINIMUM_CONFIDENCE = 0


def tesseract_available() -> bool:
    try:
        if importlib.util.find_spec("pytesseract") is None:
            return False
    except ValueError:
        return False
    return shutil.which("tesseract") is not None


class TesseractEngine:
    name = "tesseract"

    def __init__(self, languages: str = "por"):
        import pytesseract

        self.languages = languages
        self._pytesseract = pytesseract
        self._lock = threading.Lock()
        self.device = DeviceChoice("cpu", None, "Tesseract roda apenas na CPU")
        self.providers = ["Tesseract"]
        self.statistics = EngineStatistics()

    def read(self, image_bgr: np.ndarray) -> list[TextBox]:
        started = time.perf_counter()
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        with self._lock:
            data = self._pytesseract.image_to_data(gray, lang=self.languages, output_type=self._pytesseract.Output.DICT)
        lines: dict[tuple[int, int, int], list[int]] = {}
        for index, word in enumerate(data["text"]):
            if word.strip() and float(data["conf"][index]) >= MINIMUM_CONFIDENCE:
                key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
                lines.setdefault(key, []).append(index)
        boxes = []
        for indexes in lines.values():
            x0 = min(data["left"][index] for index in indexes)
            y0 = min(data["top"][index] for index in indexes)
            x1 = max(data["left"][index] + data["width"][index] for index in indexes)
            y1 = max(data["top"][index] + data["height"][index] for index in indexes)
            confidence = sum(float(data["conf"][index]) for index in indexes) / len(indexes) / 100
            text = " ".join(data["text"][index].strip() for index in indexes)
            boxes.append(TextBox(text, confidence, float(x0), float(y0), float(x1), float(y1)))
        self.statistics.add(time.perf_counter() - started)
        return boxes
