import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from legivel.ocr import devices
from legivel.ocr.adapters import GpuAdapter, preferred_adapter
from legivel.ocr.devices import DeviceChoice, package_conflict, resolve_device

IMAGE = np.zeros((10, 10, 3), np.uint8)
RX590 = GpuAdapter(0, "AMD Radeon RX590 GME", "AMD", 8170, False)
SOFTWARE = GpuAdapter(1, "Microsoft Basic Render Driver", "Microsoft", 0, True)
INTEGRATED = GpuAdapter(2, "AMD Radeon Graphics", "AMD", 512, False)
DML_PROVIDERS = ["DmlExecutionProvider", "CPUExecutionProvider"]


class TimedEngine:
    def __init__(self, choice: DeviceChoice, delays: dict[str, float], failures: set[str]):
        if choice.kind in failures:
            raise MemoryError("sem memória de vídeo")
        self.device = choice
        self.delay = delays[choice.kind]

    def read(self, image):
        import time

        time.sleep(self.delay)
        return []


def builder(delays, failures=frozenset()):
    return lambda choice: TimedEngine(choice, delays, set(failures))


@pytest.fixture(autouse=True)
def windows(monkeypatch):
    monkeypatch.setattr(devices.sys, "platform", "win32")
    monkeypatch.setattr(devices, "package_conflict", lambda: None)


def test_auto_prefers_faster_gpu():
    choice, engine = resolve_device("auto", builder({"dml": 0.001, "cpu": 0.02}), lambda: IMAGE, DML_PROVIDERS, [RX590, SOFTWARE])
    assert choice.kind == "dml"
    assert choice.adapter == RX590
    assert "mais rápida" in choice.reason
    assert engine.device == choice


def test_auto_falls_back_when_gpu_is_slower():
    choice, engine = resolve_device("auto", builder({"dml": 0.02, "cpu": 0.001}), lambda: IMAGE, DML_PROVIDERS, [RX590])
    assert choice.kind == "cpu"
    assert "mais lenta" in choice.reason
    assert engine.device.kind == "cpu"


def test_auto_falls_back_when_gpu_fails_to_start(caplog):
    choice, _ = resolve_device("auto", builder({"cpu": 0.0}, {"dml"}), lambda: IMAGE, DML_PROVIDERS, [RX590])
    assert choice.kind == "cpu"
    assert "MemoryError" in choice.reason
    assert "OCR em CPU" in caplog.text


def test_auto_without_gpu_provider_uses_cpu():
    choice, _ = resolve_device("auto", builder({"cpu": 0.0}), lambda: IMAGE, ["CPUExecutionProvider"], [RX590])
    assert choice.kind == "cpu"
    assert "nenhum provider de GPU" in choice.reason


def test_software_adapter_is_never_chosen():
    choice, _ = resolve_device("auto", builder({"dml": 0.0, "cpu": 0.1}), lambda: IMAGE, DML_PROVIDERS, [SOFTWARE])
    assert choice.kind == "cpu"
    assert "nenhum adaptador DirectML de hardware" in choice.reason


def test_dedicated_gpu_wins_over_integrated():
    assert preferred_adapter([INTEGRATED, SOFTWARE, RX590]) == RX590


def test_small_vram_falls_back():
    choice, _ = resolve_device("auto", builder({"dml": 0.0, "cpu": 0.1}), lambda: IMAGE, DML_PROVIDERS, [INTEGRATED])
    assert choice.kind == "cpu"
    assert "VRAM insuficiente" in choice.reason


def test_forced_cpu_skips_gpu():
    choice, _ = resolve_device("cpu", builder({"cpu": 0.0}, {"dml"}), lambda: IMAGE, DML_PROVIDERS, [RX590])
    assert choice.kind == "cpu"


def test_forced_gpu_keeps_gpu_even_if_slower():
    choice, _ = resolve_device("gpu", builder({"dml": 0.02, "cpu": 0.001}), lambda: IMAGE, DML_PROVIDERS, [RX590])
    assert choice.kind == "dml"


def test_package_conflict_detection():
    assert package_conflict(["onnxruntime 1.20.0"]) is None
    warning = package_conflict(["onnxruntime 1.20.0", "onnxruntime-directml 1.20.0"])
    assert "conflito" in warning
    assert ".[gpu-directml]" in warning


@pytest.mark.ocr
@pytest.mark.skipif(sys.platform != "win32", reason="DirectML só existe no Windows")
@pytest.mark.skipif(importlib.util.find_spec("rapidocr") is None, reason="RapidOCR não instalado")
def test_directml_session_runs_on_dedicated_adapter():
    import onnxruntime

    from legivel.ocr.adapters import list_adapters
    from legivel.ocr.rapid_engine import RapidOcrEngine

    if "DmlExecutionProvider" not in onnxruntime.get_available_providers():
        pytest.skip("onnxruntime-directml não instalado")
    adapter = preferred_adapter(list_adapters())
    assert adapter is not None and not adapter.software
    engine = RapidOcrEngine(DeviceChoice("dml", adapter, "teste"), Path("models"))
    assert "DmlExecutionProvider" in engine.providers
