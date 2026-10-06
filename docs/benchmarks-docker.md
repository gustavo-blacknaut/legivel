# Benchmark de OCR: CPU x GPU (DirectML)

Medido em 06/10/2026 14:26 com `scripts/benchmark.py`. Imagens sintéticas de documento
(RG fictício fotografado em perspectiva, pré-processado como no sistema) e uma página de calibração.
Cada linha é um processo novo; a primeira imagem é descartada como aquecimento e não entra na média.

## Máquina

| Item | Valor |
| --- | --- |
| CPU | AMD Ryzen 5 1600 Six-Core Processor (6 núcleos / 12 threads) |
| GPU | nenhuma |
| Driver da GPU | - |
| RAM da VM do WSL2 | 9.7 GB |
| Sistema | Linux 6.18.40.1-microsoft-standard-WSL2 (build #1 SMP PREEMPT_DYNAMIC Fri Jul 31 22:12:15 UTC 2026) |
| Python | 3.12.15 |
| Pacotes | onnxruntime 1.30.0, rapidocr 3.9.2 |

## Resultados

| Dispositivo | Lote | Tempo médio por imagem | Mediana | Imagens/s | Inicialização | Pico de RAM | Pico de VRAM | Providers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CPU | 1 | 1973 ms | 1973 ms | 0.51 | 1.3 s | 1245 MB | - | CPUExecutionProvider |
| CPU | 8 | 2090 ms | 2132 ms | 0.48 | 1.1 s | 1582 MB | - | CPUExecutionProvider |
| CPU | 32 | 1808 ms | 1846 ms | 0.55 | 1.1 s | 1566 MB | - | CPUExecutionProvider |

## Comparação

