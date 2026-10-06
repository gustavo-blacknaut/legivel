# Legível

[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-1d6b47)](LICENSE)

Lê RG, CNH e cartão CPF a partir de fotos, extrai os campos, valida o CPF e monta um cadastro de pessoas para revisão. Roda inteiro num servidor próprio: o OCR é local, as imagens ficam criptografadas em disco e nada é enviado para serviços externos.

Existe porque digitar dados de documentos à mão é lento e sujeito a erro, e os serviços prontos de OCR exigem mandar imagens de documentos de terceiros para fora, o que complica a LGPD.

<img src="docs/screenshots/fluxo.gif" alt="Envio de um RG fictício, revisão dos campos e cadastro da pessoa" width="760">

| Desktop | Celular |
| --- | --- |
| <img src="docs/screenshots/1280/revisao.png" alt="Revisão de um documento com confiança por campo" width="520"> | <img src="docs/screenshots/375/pessoas.png" alt="Lista de pessoas no celular" width="220"> |
| <img src="docs/screenshots/1280/pessoas-escuro.png" alt="Lista de pessoas no tema escuro" width="520"> | <img src="docs/screenshots/375/apagar.png" alt="Confirmação de exclusão em bottom sheet" width="220"> |

Todas as telas em 360, 375, 768, 1024, 1280 e 1920 px estão em [docs/screenshots](docs/screenshots). Os documentos que aparecem são fictícios, gerados por `apps/api/tests/synthetic.py`.

## O que faz

- Identifica o tipo do documento, corrige perspectiva e orientação, separa frente e verso e recorta foto, assinatura e polegar.
- Mostra a confiança do OCR em cada campo; o CPF passa pelo dígito verificador e é relido quando não fecha.
- Consolida pessoas por CPF. Lista com busca, filtros na URL, paginação e exclusão com confirmação digitada.
- Envio remoto: um link de uso único para a própria pessoa fotografar o documento pelo celular.
- Contas por e-mail com convite, confirmação de e-mail, redefinição de senha, 2FA (TOTP), papéis configuráveis (administrador, revisor, leitor), bloqueio temporário e sessões revogáveis.
- Auditoria de todas as ações, inclusive visualizações, com usuário, IP e horário.
- Retenção com exclusão automática, compressão opcional dos originais e limites de envio configuráveis em execução.
- Interface em português e inglês, tema claro e escuro, utilizável no celular com uma mão.

## Como funciona

```
apps/api   FastAPI, SQLAlchemy 2, Alembic, RapidOCR (PP-OCRv5 em ONNX Runtime) e Tesseract de reserva
apps/web   Next.js 16 (App Router), React 19, TanStack Query, Zod, CSS Modules
```

O navegador fala só com o Next. Ele encaminha `/api/*` para a FastAPI por rewrites, então não há CORS e os cookies de sessão (HttpOnly, SameSite=Strict) são emitidos pela própria API. Os tipos do cliente são gerados do OpenAPI da FastAPI.

O banco padrão no Docker é PostgreSQL. SQLite continua suportado pelo mesmo código e pelas mesmas migrations, útil para rodar sem Docker; os testes passam nos dois.

## Rodar com Docker

Requisitos: Docker com Compose v2.

```bash
git clone https://github.com/gustavo-blacknaut/legivel.git
cd legivel
cp .env.example .env
```

Gere as senhas do banco e as chaves. Elas ficam em arquivos na pasta `secrets/`, fora do `.env` e fora do Git:

```bash
sh scripts/gerar-segredos.sh
```

No Windows: `powershell -ExecutionPolicy Bypass -File scripts\gerar-segredos.ps1`. Guarde uma cópia de `secrets/encryption_key` fora do servidor: sem ela as imagens e os dados cifrados não podem ser lidos.

Quem já tinha uma instalação com as chaves no `.env` roda o mesmo script: ele copia os valores existentes para `secrets/`. Depois apague `POSTGRES_PASSWORD`, `LEGIVEL_SECRET_KEY` e `LEGIVEL_ENCRYPTION_KEY` do `.env`.

Depois:

```bash
docker compose up -d --build
```

Abra `http://127.0.0.1:8090`. Na primeira visita aparece a configuração inicial, que cria o administrador. Os demais usuários entram por convite em *Usuários*.

Só a interface é publicada no host. Para acessar de outros aparelhos da rede, use `LEGIVEL_BIND=0.0.0.0`. Para expor na internet, coloque um proxy com HTTPS na frente e ligue `LEGIVEL_PRODUCTION=true`, `LEGIVEL_SECURE_COOKIES=true` e `LEGIVEL_PUBLIC_URL` com o endereço `https://`. Com `LEGIVEL_PRODUCTION=true` a API se recusa a subir se faltar algum desses itens.

E-mail em desenvolvimento: `docker compose --profile dev up -d mailpit` e, no `.env`, `LEGIVEL_SMTP_HOST=mailpit`, `LEGIVEL_SMTP_PORT=1025`, `LEGIVEL_SMTP_SECURITY=none`, `LEGIVEL_SMTP_FROM=legivel@exemplo.com.br`. As mensagens aparecem em `http://127.0.0.1:8025`. Sem SMTP, convites e links de redefinição aparecem na tela para o administrador copiar.

Todas as variáveis estão em [.env.example](.env.example) e [docs/configuracao.md](docs/configuracao.md).

## GPU com Docker no Windows

O Docker Desktop não repassa GPUs AMD e Intel para containers, então no Docker o OCR roda na CPU. Para usar a placa de vídeo sem abrir mão do Docker, deixe o PostgreSQL e a interface no Docker e rode só a API no Windows:

```powershell
docker compose stop api
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build postgres web
.\scripts\api-gpu.ps1
```

O script lê o `.env`, aponta a API para o PostgreSQL publicado em `127.0.0.1:5432` e para a pasta `storage`, que é a mesma montada no container, e sobe a API em `127.0.0.1:8000` com `LEGIVEL_OCR_DEVICE=auto`. Ele usa o ambiente `.venv` da instalação nativa abaixo.

Para voltar ao modo só Docker: `docker compose up -d --build`. O `--build` é necessário porque o endereço da API é gravado no build da interface.

## Rodar no Windows sem Docker

É o caminho para usar a GPU: o Docker Desktop não repassa GPUs AMD e Intel para containers.

Requisitos: Python 3.12, Node.js 20.9 ou mais novo, driver de vídeo atualizado.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "apps/api[gpu-directml,tesseract,dev]"
copy .env.example apps\api\.env
python -m legivel.cli generate-key
python -m legivel.cli generate-key
```

Cole as chaves em `LEGIVEL_SECRET_KEY` e `LEGIVEL_ENCRYPTION_KEY` no `apps\api\.env`. O banco padrão fora do Docker é SQLite em `apps\api\data`. Então, em um terminal:

```powershell
cd apps\api
mkdir data
python -m legivel.cli download-models
alembic upgrade head
uvicorn legivel.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

E em outro:

```powershell
cd apps\web
npm ci
npm run build
npm run start
```

A interface fica em `http://127.0.0.1:3000`. Para CPU sem GPU, troque `gpu-directml` por `cpu`; para NVIDIA, `gpu-cuda`. Os três extras não podem ser instalados juntos.

`python -m legivel.cli ocr-status` mostra o dispositivo escolhido, os providers do ONNX Runtime e a placa de vídeo usada. A mesma informação, com o tempo médio por imagem, aparece em *Configurações > Motor de OCR*.

## Hardware testado

Medido com `scripts/benchmark.py` em imagens sintéticas. Relatórios completos: [docs/benchmarks.md](docs/benchmarks.md) (Windows nativo) e [docs/benchmarks-docker.md](docs/benchmarks-docker.md) (Docker, CPU).

| CPU | GPU | RAM | Sistema | Tempo por imagem, CPU | Tempo por imagem, GPU |
| --- | --- | --- | --- | --- | --- |
| AMD Ryzen 5 1600AF (6 núcleos / 12 threads) | AMD Radeon RX 590 GME, 8 GB, driver 31.0.21924.61 | 19,9 GB | Windows 10 Pro 22H2 | 2.743 a 4.858 ms nativo, 1.772 a 2.107 ms no Docker | 829 a 852 ms (DirectML) |

Os números nativos são da última rodada, feita com o Docker do Legível ligado na mesma máquina. Somando as três rodadas medidas, a CPU ficou entre 1.854 e 4.858 ms por imagem e a GPU entre 574 e 852 ms; a GPU foi mais rápida em todos os lotes de todas as rodadas.

Suporte a GPU: AMD, Intel e NVIDIA via DirectML no Windows (só a AMD acima foi testada) e NVIDIA via CUDA (implementado, não testado). Detalhes e solução de problemas em [docs/gpu.md](docs/gpu.md).

## Backup e restauração

O que precisa de backup: o banco, as imagens (pasta `storage`) e a pasta `secrets/`. Os scripts abaixo cuidam dos dois primeiros; guarde `secrets/` à parte, fora do servidor, porque sem `secrets/encryption_key` as imagens e os dados cifrados são ilegíveis e sem `secrets/backup_passphrase` o backup não abre.

```bash
sh scripts/backup.sh
```

Gera `backups/legivel-AAAAMMDDTHHMMSSZ.tar.gz.gpg`: dump do PostgreSQL e cópia das imagens, com somas SHA-256, cifrados com AES-256 (GnuPG, senha em `secrets/backup_passphrase`). Pode receber outra pasta de destino como argumento. Para agendar, uma linha no cron basta, por exemplo `15 3 * * * cd /opt/legivel && sh scripts/backup.sh`; copie os arquivos para fora do servidor.

Conferir um backup sem tocar na instalação (restaura num PostgreSQL temporário, confere as somas e mostra as contagens):

```bash
sh scripts/restaurar-backup.sh backups/legivel-20261005T031500Z.tar.gz.gpg --verificar
```

Restaurar de verdade, substituindo o banco e as imagens (num servidor novo, primeiro copie o `.env` e a pasta `secrets/`):

```bash
sh scripts/restaurar-backup.sh backups/legivel-20261005T031500Z.tar.gz.gpg --confirmar
```

O script para a API e a interface, restaura o banco e as imagens e sobe tudo de novo; o serviço `migrate` reaplica as migrações e as permissões do usuário da aplicação. Requisitos no host: Docker, `gpg`, `tar` e `sha256sum`.

Migrar uma instalação SQLite para PostgreSQL:

```bash
docker compose run --rm --no-deps -v "$PWD/data:/import" api python -m legivel.cli sqlite-to-postgres --source sqlite:////import/legivel.db --target "postgresql://legivel:SENHA@postgres:5432/legivel"
```

O comando exige o PostgreSQL vazio, copia todas as tabelas, ajusta as sequências e confere as contagens. As imagens não mudam de lugar; copie o diretório de armazenamento para a pasta `storage`.

## Testes

```bash
docker compose --profile tests run --rm tests
```

Roda o lint e a suíte da API em PostgreSQL e em SQLite. Fora do Docker:

```bash
cd apps/api && pytest
cd apps/web && npm run lint && npm run typecheck && npm test
cd apps/web && npx playwright install chromium && npx playwright test --project=setup --project=flows --project=responsive
```

O Playwright sobe a API com dados fictícios e um build de produção da interface. O teste de responsividade falha se qualquer rota tiver rolagem horizontal em 360, 375, 768, 1024, 1280 e 1920 px, e em 640 px (1280 com zoom de 200%), ou se um alvo de toque tiver menos de 44 px em telas pequenas. `SCREENSHOTS=1 npx playwright test --project=setup --project=screenshots` regenera as capturas desta página; `python scripts/flow_gif.py` monta o GIF.

O CI também roda, a cada push e toda segunda-feira, gitleaks no histórico do Git, Trivy nas dependências, nos Dockerfiles e nas imagens, e CodeQL no Python e no TypeScript. Para barrar segredos antes do commit, instale o [pre-commit](https://pre-commit.com) e rode `pre-commit install`; o gancho do gitleaks já está em `.pre-commit-config.yaml`.

## Limitações

- RG, CNH e CPF brasileiros. Os layouts de RG variam por estado; modelos muito diferentes dos testados (SP, MG e o modelo nacional) podem sair com campos vazios e precisam de revisão manual.
- A qualidade do OCR depende da foto. Documentos plastificados com reflexo e fotos tremidas são a maior fonte de erro.
- GPU AMD e Intel só no Windows nativo. No Docker o OCR roda sempre em CPU.
- O caminho CUDA não foi testado por falta de placa NVIDIA.
- A API roda em um processo; o limite de tentativas por IP fica em memória e zera ao reiniciar (o bloqueio por conta fica no banco).
- O motivo da escolha de dispositivo de OCR em *Configurações* aparece em português mesmo com a interface em inglês.
- A verificação de sessão no Next (`proxy.ts`) só checa a presença do cookie; a validação real é feita pela API em cada requisição.

## Estrutura

```
apps/api/legivel/
  auth/        contas, sessões, convites, 2FA e permissões
  db/          modelos, sessão e cópia SQLite para PostgreSQL
  imaging/     pré-processamento e recortes
  mail/        envio por SMTP e textos dos e-mails
  ocr/         motores, escolha de dispositivo e status
  parsers/     um parser por tipo de documento
  services/    documentos, pessoas, auditoria, retenção e configurações
apps/api/migrations/   migrations Alembic
apps/web/src/app/      rotas do App Router
apps/web/e2e/          testes Playwright
docs/                  configuração, GPU, benchmarks e capturas
```

## Licença

[MIT](LICENSE)
