# Benchmark de OCR: CPU x GPU (DirectML)

Medido em 06/10/2026 11:19 com `scripts/benchmark.py`. Imagens sintéticas de documento
(RG fictício fotografado em perspectiva, pré-processado como no sistema) e uma página de calibração.
Cada linha é um processo novo; a primeira imagem é descartada como aquecimento e não entra na média.

## Máquina

| Item | Valor |
| --- | --- |
| CPU | AMD Ryzen 5 1600 Six-Core Processor (6 núcleos / 12 threads) |
| GPU | AMD Radeon RX590 GME (8170 MB) |
| Driver da GPU | 31.0.21924.61 |
| RAM total | 19.9 GB |
| Sistema | Microsoft Windows 10 Pro (build 10.0.19045) |
| Python | 3.12.15 |
| Pacotes | onnxruntime-directml 1.24.4, rapidocr 3.9.2 |

## Resultados

| Dispositivo | Lote | Tempo médio por imagem | Mediana | Imagens/s | Inicialização | Pico de RAM | Pico de VRAM | Providers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CPU | 1 | 2307 ms | 2307 ms | 0.43 | 2.0 s | 1127 MB | - | CPUExecutionProvider |
| CPU | 8 | 1951 ms | 1955 ms | 0.51 | 2.4 s | 1379 MB | - | CPUExecutionProvider |
| CPU | 32 | 1939 ms | 2044 ms | 0.52 | 1.7 s | 1395 MB | - | CPUExecutionProvider |
| GPU (DirectML) | 1 | 530 ms | 530 ms | 1.89 | 2.4 s | 349 MB | 1041 MB | CPUExecutionProvider, DmlExecutionProvider |
| GPU (DirectML) | 8 | 445 ms | 443 ms | 2.25 | 2.5 s | 525 MB | 1042 MB | CPUExecutionProvider, DmlExecutionProvider |
| GPU (DirectML) | 32 | 494 ms | 488 ms | 2.02 | 2.4 s | 556 MB | 1074 MB | CPUExecutionProvider, DmlExecutionProvider |

## Comparação

- Lote de 1: CPU 2307 ms x GPU 530 ms por imagem (GPU 4.3x mais rápida)
- Lote de 8: CPU 1951 ms x GPU 445 ms por imagem (GPU 4.4x mais rápida)
- Lote de 32: CPU 1939 ms x GPU 494 ms por imagem (GPU 3.9x mais rápida)
