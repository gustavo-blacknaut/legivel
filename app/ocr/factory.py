from functools import lru_cache

from app.ocr.base import OcrEngine


@lru_cache
def get_ocr_engine(engine_name: str, device: str = "cpu") -> OcrEngine:
    if engine_name == "paddle":
        from app.ocr.paddle_engine import PaddleOcrEngine

        return PaddleOcrEngine(device=device)
    raise ValueError(f"Motor de OCR desconhecido: {engine_name}")
