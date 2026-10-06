import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata

import numpy as np

from legivel.ocr.adapters import GpuAdapter, list_adapters, preferred_adapter

logger = logging.getLogger("legivel.ocr")

ONNX_PACKAGES = ("onnxruntime", "onnxruntime-directml", "onnxruntime-gpu")
DIRECTML_PROVIDER = "DmlExecutionProvider"
CUDA_PROVIDER = "CUDAExecutionProvider"
MINIMUM_VRAM_MB = 1024
TIMED_RUNS = 2


@dataclass(frozen=True)
class DeviceChoice:
    kind: str
    adapter: GpuAdapter | None
    reason: str
    gpu_ms: float | None = None
    cpu_ms: float | None = None

    @property
    def label(self) -> str:
        if self.kind == "dml":
            return f"GPU via DirectML ({self.adapter.name if self.adapter else 'adaptador padrão'})"
        if self.kind == "cuda":
            return "GPU via CUDA"
        return "CPU"


def installed_onnx_packages() -> list[str]:
    installed = []
    for package in ONNX_PACKAGES:
        try:
            installed.append(f"{package} {metadata.version(package)}")
        except metadata.PackageNotFoundError:
            continue
    return installed


def package_conflict(installed: list[str] | None = None) -> str | None:
    packages = installed if installed is not None else installed_onnx_packages()
    if len(packages) > 1:
        names = ", ".join(packages)
        return (
            f"Pacotes do ONNX Runtime em conflito: {names}. Eles sobrescrevem os mesmos arquivos. "
            "Desinstale todos e reinstale apenas um extra: .[cpu], .[gpu-directml] ou .[gpu-cuda]."
        )
    return None


def available_providers() -> list[str]:
    try:
        import onnxruntime
    except ImportError:
        return []
    return list(onnxruntime.get_available_providers())


def time_engine(engine, image: np.ndarray) -> float:
    engine.read(image)
    started = time.perf_counter()
    for _ in range(TIMED_RUNS):
        engine.read(image)
    return (time.perf_counter() - started) / TIMED_RUNS * 1000


def gpu_kind(providers: list[str]) -> str | None:
    if DIRECTML_PROVIDER in providers and sys.platform == "win32":
        return "dml"
    if CUDA_PROVIDER in providers:
        return "cuda"
    return None


def resolve_device(
    requested: str,
    build_engine: Callable[["DeviceChoice"], object],
    calibration_image: Callable[[], np.ndarray],
    providers: list[str] | None = None,
    adapters: list[GpuAdapter] | None = None,
) -> tuple[DeviceChoice, object]:
    providers = providers if providers is not None else available_providers()
    if conflict := package_conflict():
        logger.warning(conflict)
    cpu_choice = DeviceChoice("cpu", None, "CPU escolhida na configuração")
    if requested == "cpu":
        engine = build_engine(cpu_choice)
        finalize(engine, cpu_choice)
        return cpu_choice, engine
    kind = gpu_kind(providers)
    if kind is None:
        reason = f"nenhum provider de GPU disponível no ONNX Runtime (providers: {', '.join(providers) or 'nenhum'})"
        return fallback(reason, build_engine)
    adapter = None
    if kind == "dml":
        adapter = preferred_adapter(adapters if adapters is not None else list_adapters())
        if adapter is None:
            return fallback("nenhum adaptador DirectML de hardware encontrado", build_engine)
        if adapter.dedicated_memory_mb < MINIMUM_VRAM_MB:
            return fallback(f"VRAM insuficiente em {adapter.name} ({adapter.dedicated_memory_mb} MB)", build_engine)
    gpu_candidate = DeviceChoice(kind, adapter, "")
    try:
        gpu_engine = build_engine(gpu_candidate)
        gpu_ms = time_engine(gpu_engine, calibration_image())
    except Exception as error:
        return fallback(f"falha ao iniciar a GPU: {type(error).__name__}: {error}", build_engine)
    if requested == "gpu":
        choice = DeviceChoice(
            kind, adapter, f"GPU escolhida na configuração ({gpu_ms:.0f} ms por imagem no teste inicial)", gpu_ms
        )
        logger.info("OCR em %s: %s", choice.label, choice.reason)
        finalize(gpu_engine, choice)
        return choice, gpu_engine
    cpu_engine = build_engine(cpu_choice)
    cpu_ms = time_engine(cpu_engine, calibration_image())
    if gpu_ms >= cpu_ms:
        choice = DeviceChoice(
            "cpu", adapter, f"GPU mais lenta no teste inicial ({gpu_ms:.0f} ms contra {cpu_ms:.0f} ms na CPU)", gpu_ms, cpu_ms
        )
        logger.warning("OCR em CPU: %s", choice.reason)
        finalize(cpu_engine, choice)
        return choice, cpu_engine
    choice = DeviceChoice(
        kind, adapter, f"GPU mais rápida no teste inicial ({gpu_ms:.0f} ms contra {cpu_ms:.0f} ms na CPU)", gpu_ms, cpu_ms
    )
    logger.info("OCR em %s: %s", choice.label, choice.reason)
    finalize(gpu_engine, choice)
    return choice, gpu_engine


def fallback(reason: str, build_engine: Callable[[DeviceChoice], object]) -> tuple[DeviceChoice, object]:
    choice = DeviceChoice("cpu", None, reason)
    logger.warning("OCR em CPU: %s", reason)
    engine = build_engine(choice)
    finalize(engine, choice)
    return choice, engine


def finalize(engine, choice: DeviceChoice) -> None:
    engine.device = choice
    statistics = getattr(engine, "statistics", None)
    if statistics is not None:
        engine.statistics = type(statistics)()
