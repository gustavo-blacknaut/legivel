import argparse
import json
import platform
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BATCHES = (1, 8, 32)
SAMPLE_INTERVAL = 0.05


def synthetic_documents(count: int) -> list:
    from legivel.imaging.preprocess import prepare_image
    from legivel.ocr.calibration import calibration_document
    from tests.synthetic import FICTITIOUS_RG, encode_jpeg, photograph, render_rg_back

    variants = []
    for index in range(min(count, 8)):
        values = dict(FICTITIOUS_RG, rg_number=f"{10 + index}.217.395-{index}")
        photo = photograph(render_rg_back(values), angle_degrees=3 + index * 2, tilt=0.02 + index * 0.01)
        variants.append(prepare_image(encode_jpeg(photo)).ocr_image)
    variants.append(calibration_document())
    return [variants[index % len(variants)] for index in range(count)]


class PeakSampler:
    def __init__(self, adapter_index: int | None):
        import psutil

        self.process = psutil.Process()
        self.adapter_index = adapter_index
        self.peak_rss = 0
        self.peak_vram = 0.0
        self._running = True
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        from legivel.ocr.adapters import video_memory_in_use_mb

        while self._running:
            self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
            if self.adapter_index is not None:
                self.peak_vram = max(self.peak_vram, video_memory_in_use_mb(self.adapter_index) or 0.0)
            time.sleep(SAMPLE_INTERVAL)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._running = False
        self._thread.join()


def run_single(device: str, batch: int) -> dict:
    from legivel.ocr.adapters import list_adapters, preferred_adapter
    from legivel.ocr.devices import DeviceChoice
    from legivel.ocr.rapid_engine import RapidOcrEngine

    adapter = preferred_adapter(list_adapters()) if device == "dml" else None
    images = synthetic_documents(batch)
    with PeakSampler(adapter.index if adapter else None) as sampler:
        started = time.perf_counter()
        engine = RapidOcrEngine(DeviceChoice(device, adapter, "benchmark"), ROOT / "models")
        init_seconds = time.perf_counter() - started
        engine.read(images[0])
        durations = []
        lines = 0
        for image in images:
            started = time.perf_counter()
            lines += len(engine.read(image))
            durations.append(time.perf_counter() - started)
    return {
        "device": device,
        "batch": batch,
        "providers": engine.providers,
        "adapter": adapter.name if adapter else None,
        "init_s": init_seconds,
        "mean_ms": statistics.mean(durations) * 1000,
        "median_ms": statistics.median(durations) * 1000,
        "total_s": sum(durations),
        "images_per_s": len(durations) / sum(durations),
        "peak_ram_mb": sampler.peak_rss / (1024 * 1024),
        "peak_vram_mb": sampler.peak_vram if adapter else None,
        "lines_per_image": lines / len(images),
    }


def powershell(command: str) -> str:
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=60
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def environment() -> dict:
    from importlib import metadata

    import psutil

    from legivel.ocr.adapters import list_adapters, preferred_adapter

    adapter = preferred_adapter(list_adapters())
    info = {
        "cpu": linux_cpu_name() or platform.processor(),
        "cores": f"{psutil.cpu_count(logical=False)} núcleos / {psutil.cpu_count()} threads",
        "ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        "os": f"{platform.system()} {platform.release()} (build {platform.version()})",
        "python": platform.python_version(),
        "gpu": f"{adapter.name} ({adapter.dedicated_memory_mb} MB)" if adapter else "nenhuma",
        "packages": {
            name: metadata.version(name) for name in ("onnxruntime-directml", "onnxruntime", "rapidocr") if is_installed(name)
        },
    }
    if sys.platform == "win32":
        info["cpu"] = powershell("(Get-CimInstance Win32_Processor).Name") or info["cpu"]
        info["os"] = powershell("(Get-CimInstance Win32_OperatingSystem).Caption") + f" (build {platform.version()})"
        info["driver"] = powershell(
            "Get-CimInstance Win32_VideoController"
            " | Where-Object { $_.AdapterCompatibility -like '*Advanced Micro*' -or $_.Name -like '*Radeon*' }"
            " | Select-Object -First 1 | ForEach-Object { $_.DriverVersion }"
        )
    return info


def linux_cpu_name() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return ""
    for line in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return ""


def is_installed(name: str) -> bool:
    from importlib import metadata

    try:
        metadata.version(name)
        return True
    except metadata.PackageNotFoundError:
        return False


def markdown(results: list[dict], env: dict) -> str:
    lines = [
        "# Benchmark de OCR: CPU x GPU (DirectML)",
        "",
        f"Medido em {datetime.now():%d/%m/%Y %H:%M} com `scripts/benchmark.py`. Imagens sintéticas de documento",
        "(RG fictício fotografado em perspectiva, pré-processado como no sistema) e uma página de calibração.",
        "Cada linha é um processo novo; a primeira imagem é descartada como aquecimento e não entra na média.",
        "",
        "## Máquina",
        "",
        "| Item | Valor |",
        "| --- | --- |",
        f"| CPU | {env['cpu']} ({env['cores']}) |",
        f"| GPU | {env['gpu']} |",
        f"| Driver da GPU | {env.get('driver', '-')} |",
        f"| RAM {'da VM do WSL2' if 'WSL' in env['os'] else 'total'} | {env['ram_gb']} GB |",
        f"| Sistema | {env['os']} |",
        f"| Python | {env['python']} |",
        f"| Pacotes | {', '.join(f'{name} {version}' for name, version in env['packages'].items())} |",
        "",
        "## Resultados",
        "",
        "| Dispositivo | Lote | Tempo médio por imagem | Mediana | Imagens/s | Inicialização"
        " | Pico de RAM | Pico de VRAM | Providers |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        device = "GPU (DirectML)" if result["device"] == "dml" else "CPU"
        vram = f"{result['peak_vram_mb']:.0f} MB" if result["peak_vram_mb"] is not None else "-"
        lines.append(
            f"| {device} | {result['batch']} | {result['mean_ms']:.0f} ms | {result['median_ms']:.0f} ms"
            f" | {result['images_per_s']:.2f} |"
            f" {result['init_s']:.1f} s | {result['peak_ram_mb']:.0f} MB | {vram} | {', '.join(result['providers'])} |"
        )
    lines += ["", "## Comparação", ""]
    for batch in BATCHES:
        cpu = next((item for item in results if item["device"] == "cpu" and item["batch"] == batch), None)
        gpu = next((item for item in results if item["device"] == "dml" and item["batch"] == batch), None)
        if cpu and gpu:
            ratio = cpu["mean_ms"] / gpu["mean_ms"]
            verdict = f"GPU {ratio:.1f}x mais rápida" if ratio > 1 else f"CPU {1 / ratio:.1f}x mais rápida"
            lines.append(f"- Lote de {batch}: CPU {cpu['mean_ms']:.0f} ms x GPU {gpu['mean_ms']:.0f} ms por imagem ({verdict})")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara o OCR em CPU e em GPU via DirectML")
    parser.add_argument("--single", nargs=2, metavar=("DEVICE", "BATCH"))
    parser.add_argument("--devices", default="cpu,dml")
    parser.add_argument("--output", default=str(ROOT.parent.parent / "docs" / "benchmarks.md"))
    arguments = parser.parse_args()
    if arguments.single:
        print(json.dumps(run_single(arguments.single[0], int(arguments.single[1]))))
        return
    results = []
    for device in arguments.devices.split(","):
        for batch in BATCHES:
            completed = subprocess.run(
                [sys.executable, __file__, "--single", device, str(batch)], capture_output=True, text=True, cwd=ROOT
            )
            if completed.returncode != 0:
                print(f"{device} lote {batch} falhou:\n{completed.stderr[-2000:]}")
                continue
            result = json.loads(completed.stdout.strip().splitlines()[-1])
            results.append(result)
            print(
                f"{device} lote {batch}: {result['mean_ms']:.0f} ms/imagem,"
                f" RAM {result['peak_ram_mb']:.0f} MB, VRAM {result['peak_vram_mb']}"
            )
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown(results, environment()), encoding="utf-8", newline="\n")
    print(f"Relatório salvo em {output}")


if __name__ == "__main__":
    main()
