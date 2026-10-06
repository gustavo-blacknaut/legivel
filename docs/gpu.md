# GPU e desempenho do OCR

## Requisitos

| | Mínimo | Recomendado |
| --- | --- | --- |
| Processador | x86-64 com 4 núcleos e suporte a AVX | 6 núcleos ou mais |
| Memória RAM | 4 GB livres (o OCR em CPU chegou a 1,6 GB de pico no benchmark) | 8 GB ou mais |
| Placa de vídeo | Não é necessária | GPU compatível com DirectML 12 (AMD, Intel ou NVIDIA) no Windows, ou NVIDIA com CUDA |
| Memória de vídeo | — | 2 GB ou mais (o OCR usou cerca de 1,1 GB de VRAM no benchmark) |
| Disco | 3 GB (imagem Docker de 1,5 GB, mais documentos) | 10 GB ou mais, conforme o volume de imagens guardadas |
| Python | 3.12 (sem Docker) | 3.12 |
| Sistema | Windows 10 build 18362 (1903) ou superior, ou Linux x86-64 | Windows 10 22H2 / Windows 11, ou Ubuntu 22.04+ |
| Docker | Docker Desktop com WSL2, ou Docker Engine + Compose v2 | — |

## Hardware testado

Valores medidos com `apps/api/scripts/benchmark.py`, com imagens sintéticas de documento. Relatórios completos em [benchmarks.md](benchmarks.md) (Windows nativo, CPU e GPU) e [benchmarks-docker.md](benchmarks-docker.md) (Docker, só CPU).

| CPU | GPU | RAM | Sistema | Driver da GPU | Python | Tempo médio por imagem, CPU | Tempo médio por imagem, GPU |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AMD Ryzen 5 1600AF (6 núcleos / 12 threads) | AMD Radeon RX 590 GME, 8 GB | 19,9 GB | Windows 10 Pro 22H2, build 19045 | 31.0.21924.61 (Adrenalin 26.1.1) | 3.12.15 | 2.743 a 4.858 ms (nativo) · 1.772 a 2.107 ms (Docker) | 829 a 852 ms (DirectML, nativo) |

As faixas cobrem os lotes de 1, 8 e 32 imagens da última rodada, feita com o Docker ligado na mesma máquina. Rodadas anteriores mediram 1.854 a 3.032 ms na CPU e 574 a 776 ms na GPU. Em todas as rodadas e em todos os lotes a GPU foi mais rápida, de 2,4 a 5,9 vezes.

## Suporte a GPU

O OCR roda com ONNX Runtime e modelos PP-OCRv5 convertidos para ONNX (RapidOCR). A variável `LEGIVEL_OCR_DEVICE` aceita:

- `auto` (padrão): testa a GPU na inicialização. Se ela não iniciar, se não houver VRAM suficiente ou se for mais lenta que a CPU num teste rápido, usa a CPU e registra o motivo no log e na tela de Configurações.
- `cpu`: sempre CPU.
- `gpu`: usa a GPU mesmo que a CPU seja mais rápida; se não houver GPU disponível, cai para a CPU e informa o motivo.

| Plataforma | Backend | Extra de instalação | Situação |
| --- | --- | --- | --- |
| AMD no Windows | DirectML | `.[gpu-directml]` | Testado na RX 590 (Polaris), driver 31.0.21924.61 |
| Intel no Windows | DirectML | `.[gpu-directml]` | Não testado; usa o mesmo caminho da AMD |
| NVIDIA no Windows | DirectML | `.[gpu-directml]` | Não testado; usa o mesmo caminho da AMD |
| NVIDIA no Linux ou Windows | CUDA | `.[gpu-cuda]` | Implementado e não testado (sem placa NVIDIA disponível) |
| AMD no Linux | ROCm | — | Não suportado; a RX 590 (Polaris) não é aceita pelas versões atuais do ROCm |
| Qualquer CPU x86-64 | CPU | `.[cpu]` | Testado, nativo no Windows e no Docker |
| Docker no Windows | CPU | imagem padrão | Testado. O Docker Desktop não repassa GPUs AMD ou Intel para o container, então o modo GPU roda nativo |

O motor alternativo é o Tesseract (`LEGIVEL_OCR_ENGINE=tesseract`, extra `.[tesseract]` e o programa `tesseract` com o idioma `por`). Ele também é usado automaticamente quando o RapidOCR não consegue iniciar. A imagem Docker já traz o Tesseract instalado.

## Como verificar se a GPU está sendo usada

- **Na interface:** em *Configurações > Motor de OCR* aparecem o dispositivo em uso, o motivo da escolha, os providers ativos do ONNX Runtime, o adaptador de vídeo usado (e os demais adaptadores do sistema) e o tempo médio por leitura. Com a GPU ativa, os providers incluem `DmlExecutionProvider` e o adaptador é a placa dedicada.
- **No terminal:**

```powershell
python -m legivel.cli ocr-status
```

- **No log do servidor:** na inicialização aparece uma linha como `OCR em GPU via DirectML (AMD Radeon RX590 GME): GPU mais rápida no teste inicial (229 ms contra 908 ms na CPU)`.
- **No Gerenciador de Tarefas:** na aba *Desempenho*, a GPU dedicada mostra uso de "Compute" ou "3D" e memória dedicada ocupada enquanto documentos são processados.
- **Benchmark:** `cd apps/api && python scripts/benchmark.py` mede CPU e GPU na sua máquina e grava `docs/benchmarks.md`.


## Solução de problemas

**Driver desatualizado.** Sintomas: o modo `auto` registra "falha ao iniciar a GPU" ou `DmlExecutionProvider` não aparece entre os providers. O DirectML exige driver com suporte a DirectX 12. Atualize pelo AMD Software (Adrenalin), Intel Driver & Support Assistant ou GeForce Experience, reinicie e confira com `python -m legivel.cli ocr-status`.

**Conflito entre `onnxruntime` e `onnxruntime-directml`.** Os dois pacotes instalam os mesmos arquivos e o último instalado sobrescreve o outro, o que pode fazer o DirectML sumir sem erro. O sistema detecta e mostra um aviso no `ocr-status`, no log e na tela de Configurações. Para corrigir, desinstale todos e reinstale apenas um extra:

```powershell
pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu
pip install -e "apps/api[gpu-directml]"
```

Para voltar à CPU, troque o último comando por `pip install -e "apps/api[cpu]"`.

**Falta de VRAM.** O OCR usou cerca de 1,1 GB de VRAM no benchmark. Se a placa tiver menos de 1 GB dedicado, o modo `auto` usa a CPU. Se outros programas ocuparem a VRAM (jogos, editores de vídeo), a inicialização pode falhar com erro de memória; o modo `auto` então cai para a CPU e registra o motivo. Feche os programas e reinicie o servidor, ou force `LEGIVEL_OCR_DEVICE=cpu`.

**GPU integrada escolhida no lugar da dedicada.** O sistema lista os adaptadores pelo DXGI, descarta o renderizador de software da Microsoft e escolhe o adaptador com mais memória dedicada, que normalmente é a placa dedicada. Confira em *Adaptador em uso*. Se ainda assim a integrada for usada, defina em *Configurações do Windows > Sistema > Tela > Elementos gráficos* a preferência "Alto desempenho" para o `python.exe` do ambiente virtual.

**`python` abre a Microsoft Store.** O Windows tem um atalho que substitui o Python. Desative-o em *Aliases de execução do aplicativo* ou chame o Python pelo caminho completo.

## Limitações conhecidas

- O modo GPU com placas AMD e Intel só funciona no Windows nativo (DirectML). O Docker Desktop não repassa essas GPUs ao container.
- A RX 590 (Polaris) não é suportada pelo ROCm, então não há aceleração AMD no Linux para esta placa.
- O caminho CUDA está implementado, mas não foi testado por falta de uma placa NVIDIA.
- A inicialização no modo `auto` leva alguns segundos a mais, porque mede a GPU e a CPU antes de escolher.
- O DirectML processa uma imagem por vez; lotes maiores não reduziram o tempo por imagem no benchmark.
- Os pacotes `onnxruntime` e `onnxruntime-directml` não podem coexistir no mesmo ambiente.
- O pacote `onnxruntime-directml` costuma sair depois do `onnxruntime` comum; no benchmark, a CPU dentro do Docker (onnxruntime 1.30) foi um pouco mais rápida que a CPU nativa com o pacote DirectML (1.24).

