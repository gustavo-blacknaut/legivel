import pytest

from legivel.ocr.calibration import calibration_document
from legivel.ocr.tesseract_engine import TesseractEngine, tesseract_available

pytestmark = [pytest.mark.ocr, pytest.mark.skipif(not tesseract_available(), reason="Tesseract não instalado")]


def test_tesseract_fallback_reads_document():
    engine = TesseractEngine()
    text = " ".join(box.text for box in engine.read(calibration_document()))
    assert "REGISTRO GERAL" in text
    assert "12.345.678-9" in text
    assert engine.device.kind == "cpu"
    assert engine.statistics.images == 1
