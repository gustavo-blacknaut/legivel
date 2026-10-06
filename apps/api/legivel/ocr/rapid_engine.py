import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from legivel.ocr.base import TextBox
from legivel.ocr.devices import CUDA_PROVIDER, DIRECTML_PROVIDER, DeviceChoice

DETECTION_SIDE_LIMIT = 1280
RECOGNITION_MODELS = {
    "latin": "LATIN",
    "cyrillic": "CYRILLIC",
    "chinese": "CH",
    "japanese": "JAPAN",
    "korean": "KOREAN",
    "arabic": "ARABIC",
    "devanagari": "DEVANAGARI",
}


class EngineStatistics:
    def __init__(self):
        self._lock = threading.Lock()
        self.images = 0
        self.total_seconds = 0.0

    def add(self, seconds: float) -> None:
        with self._lock:
            self.images += 1
            self.total_seconds += seconds

    @property
    def average_ms(self) -> float | None:
        return self.total_seconds / self.images * 1000 if self.images else None


def physical_cores() -> int:
    try:
        import psutil

        return psutil.cpu_count(logical=False) or os.cpu_count() or 1
    except ImportError:
        return os.cpu_count() or 1


def session_providers(device: DeviceChoice) -> list:
    if device.kind == "dml":
        return [(DIRECTML_PROVIDER, {"device_id": device.adapter.index if device.adapter else 0}), "CPUExecutionProvider"]
    if device.kind == "cuda":
        return [(CUDA_PROVIDER, {"device_id": 0}), "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def session_options(device: DeviceChoice):
    import onnxruntime

    options = onnxruntime.SessionOptions()
    if device.kind == "dml":
        options.enable_mem_pattern = False
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
    else:
        options.intra_op_num_threads = physical_cores()
    return options


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self, device: DeviceChoice, model_dir: Path, pack: str = "latin"):
        self.device = device
        self.pack = pack
        self.statistics = EngineStatistics()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rapidocr")
        self._reader, self.providers = self._worker.submit(self._create, model_dir).result()

    def _create(self, model_dir: Path):
        import onnxruntime
        from rapidocr import LangDet, LangRec, ModelType, OCRVersion, RapidOCR

        model_dir.mkdir(parents=True, exist_ok=True)
        reader = RapidOCR(
            params={
                "Global.use_cls": False,
                "Global.log_level": "error",
                "Global.model_root_dir": str(model_dir),
                "Det.ocr_version": OCRVersion.PPOCRV5,
                "Det.lang_type": LangDet.CH,
                "Det.model_type": ModelType.MOBILE,
                "Det.limit_type": "max",
                "Det.limit_side_len": DETECTION_SIDE_LIMIT,
                "Rec.ocr_version": OCRVersion.PPOCRV5,
                "Rec.lang_type": getattr(LangRec, RECOGNITION_MODELS[self.pack]),
                "Rec.model_type": ModelType.MOBILE,
            }
        )
        providers = session_providers(self.device)
        active = []
        for part in (reader.text_det, reader.text_rec):
            model_path = part.session.session._model_path
            session = onnxruntime.InferenceSession(model_path, sess_options=session_options(self.device), providers=providers)
            part.session.session = session
            active.append(session.get_providers())
        if self.device.kind != "cpu" and any(self.expected_provider not in providers_list for providers_list in active):
            raise RuntimeError(f"o provider {self.expected_provider} não foi ativado (ativos: {active})")
        return reader, sorted({provider for providers_list in active for provider in providers_list})

    @property
    def expected_provider(self) -> str:
        return DIRECTML_PROVIDER if self.device.kind == "dml" else CUDA_PROVIDER

    def read(self, image_bgr: np.ndarray) -> list[TextBox]:
        return self._worker.submit(self._read_on_worker, image_bgr).result()

    def _read_on_worker(self, image_bgr: np.ndarray) -> list[TextBox]:
        started = time.perf_counter()
        result = self._reader(image_bgr)
        self.statistics.add(time.perf_counter() - started)
        boxes: list[TextBox] = []
        if result.boxes is None:
            return boxes
        for polygon, text, score in zip(result.boxes, result.txts, result.scores, strict=False):
            points = np.asarray(polygon, dtype=float).reshape(-1, 2)
            x0, y0 = points.min(axis=0)
            x1, y1 = points.max(axis=0)
            if text.strip():
                boxes.append(TextBox(text.strip(), float(score), float(x0), float(y0), float(x1), float(y1)))
        return boxes
