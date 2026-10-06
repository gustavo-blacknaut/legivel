import threading
import time
from contextlib import contextmanager

from legivel.ocr.rapid_engine import EngineStatistics

_timings: dict[int, EngineStatistics] = {}
_lock = threading.Lock()


def image_statistics(engine) -> EngineStatistics:
    with _lock:
        return _timings.setdefault(id(engine), EngineStatistics())


@contextmanager
def timed_image(engine):
    started = time.perf_counter()
    try:
        yield
    finally:
        image_statistics(engine).add(time.perf_counter() - started)
