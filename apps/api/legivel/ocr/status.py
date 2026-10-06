import sys
from pathlib import Path

from legivel.ocr.adapters import list_adapters
from legivel.ocr.devices import installed_onnx_packages, package_conflict
from legivel.ocr.factory import get_ocr_engine
from legivel.ocr.timing import image_statistics

LABELS = {
    "engine": "Motor",
    "requested_device": "Dispositivo solicitado",
    "device": "Dispositivo em uso",
    "reason": "Motivo",
    "providers": "Providers ativos",
    "adapter": "Adaptador em uso",
    "adapters": "Adaptadores do sistema",
    "packages": "Pacotes ONNX Runtime",
    "image_average_ms": "Tempo médio por imagem (ms)",
    "images": "Imagens processadas",
    "average_ms": "Tempo médio por leitura (ms)",
    "readings": "Leituras medidas",
    "warning": "Aviso",
}


def describe_engine(engine, requested: str) -> dict[str, str | float | int | None]:
    choice = getattr(engine, "device", None)
    statistics = getattr(engine, "statistics", None)
    adapters = list_adapters()
    per_image = image_statistics(engine)
    return {
        "engine": getattr(engine, "name", "desconhecido"),
        "requested_device": requested,
        "device": choice.label if choice else None,
        "device_kind": choice.kind if choice else None,
        "reason": choice.reason if choice else None,
        "providers": ", ".join(getattr(engine, "providers", [])) or None,
        "adapter": (
            f"{choice.adapter.name} ({choice.adapter.dedicated_memory_mb} MB)"
            if choice and choice.kind == "dml" and choice.adapter
            else None
        ),
        "adapters": "; ".join(
            f"{adapter.index}: {adapter.name}{' (software)' if adapter.software else ''}" for adapter in adapters
        )
        or ("indisponível fora do Windows" if sys.platform != "win32" else None),
        "packages": ", ".join(installed_onnx_packages()) or None,
        "image_average_ms": round(per_image.average_ms, 1) if per_image.average_ms else None,
        "images": per_image.images,
        "average_ms": round(statistics.average_ms, 1) if statistics and statistics.average_ms else None,
        "readings": statistics.images if statistics else 0,
        "warning": package_conflict(),
    }


def ocr_status(engine_name: str, device: str, model_dir: Path, languages: str = "por") -> dict:
    return describe_engine(get_ocr_engine(engine_name, device, model_dir, languages), device)
