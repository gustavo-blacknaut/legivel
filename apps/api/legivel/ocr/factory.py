import logging
import threading
from pathlib import Path

from legivel.ocr.base import OcrEngine
from legivel.ocr.calibration import calibration_document
from legivel.ocr.devices import DeviceChoice, resolve_device

logger = logging.getLogger("legivel.ocr")
_engines: dict[tuple[str, str, str, str], OcrEngine] = {}
_lock = threading.Lock()


def build_rapid(model_dir: Path):
    from legivel.ocr.rapid_engine import RapidOcrEngine

    def build(choice: DeviceChoice):
        return RapidOcrEngine(choice, model_dir)

    return build


def create_engine(engine_name: str, device: str, model_dir: Path, languages: str = "por") -> OcrEngine:
    if engine_name == "tesseract":
        from legivel.ocr.tesseract_engine import TesseractEngine

        return TesseractEngine(languages)
    try:
        _, engine = resolve_device(device, build_rapid(model_dir), calibration_document)
        return engine
    except Exception as error:
        from legivel.ocr.tesseract_engine import TesseractEngine, tesseract_available

        if not tesseract_available():
            raise
        logger.error("RapidOCR indisponível (%s: %s); usando Tesseract", type(error).__name__, error)
        return TesseractEngine(languages)


def get_ocr_engine(
    engine_name: str, device: str = "auto", model_dir: Path = Path("./models"), languages: str = "por"
) -> OcrEngine:
    key = (engine_name, device, str(model_dir), languages)
    with _lock:
        if key not in _engines:
            _engines[key] = create_engine(engine_name, device, model_dir, languages)
        return _engines[key]


def loaded_engines() -> list[OcrEngine]:
    with _lock:
        return list(_engines.values())
