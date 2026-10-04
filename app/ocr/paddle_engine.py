from concurrent.futures import ThreadPoolExecutor

import numpy as np

from app.ocr.base import TextBox


class PaddleOcrEngine:
    name = "paddle"

    def __init__(self, detection_side_limit: int = 1280, device: str = "cpu"):
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddle-ocr")
        self._reader = self._worker.submit(self._create_reader, detection_side_limit, device).result()
        self.device = device

    @staticmethod
    def _create_reader(detection_side_limit: int, device: str):
        from paddleocr import PaddleOCR

        return PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
            text_det_limit_type="max",
            text_det_limit_side_len=detection_side_limit,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=device,
            enable_mkldnn=device == "cpu",
        )

    def read(self, image_bgr: np.ndarray) -> list[TextBox]:
        return self._worker.submit(self._read_on_worker, image_bgr).result()

    def _read_on_worker(self, image_bgr: np.ndarray) -> list[TextBox]:
        boxes: list[TextBox] = []
        for result in self._reader.predict(image_bgr):
            for text, score, polygon in zip(result["rec_texts"], result["rec_scores"], result["rec_polys"], strict=False):
                points = np.asarray(polygon, dtype=float).reshape(-1, 2)
                x0, y0 = points.min(axis=0)
                x1, y1 = points.max(axis=0)
                if text.strip():
                    boxes.append(TextBox(text.strip(), float(score), float(x0), float(y0), float(x1), float(y1)))
        return boxes
