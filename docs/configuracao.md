# Configuração

A API lê variáveis com prefixo `LEGIVEL_` do ambiente ou de um arquivo `.env` na pasta em que roda. Tudo é validado na inicialização: valor inválido ou ausente faz a API parar com uma mensagem que cita a variável, por exemplo:

```
Configuração inválida:
  - LEGIVEL_SECRET_KEY: obrigatória, com pelo menos 32 caracteres (gere com: python -m legivel.cli generate-key)
  - LEGIVEL_UPLOAD_FORMATS: formatos aceitos: jpeg, png, webp, heic; recebido: 'jpeg,gif'
```

`python -m legivel.cli check-config` faz a mesma validação sem subir o servidor.

Qualquer variável pode vir de um arquivo: `LEGIVEL_SECRET_KEY_FILE=/run/secrets/secret_key` lê o valor de `/run/secrets/secret_key`, sem espaços nem quebra de linha no fim. Se a variável sem `_FILE` também estiver preenchida, ela vale. O Compose usa esse formato para todos os segredos (ver *Docker Compose* abaixo).

A coluna **Em execução** marca o que o administrador pode mudar em *Configurações* sem reiniciar. Nesses casos a variável é só o valor padrão; o que for salvo na tela fica no banco e vale até alguém clicar em "Usar padrão".

## Segredos e armazenamento

| Variável | Padrão | Obrigatória | Em execução | Descrição |
| --- | --- | --- | --- | --- |
| `LEGIVEL_SECRET_KEY` | — | sim | não | Assina os cookies de sessão e cifra o segredo do 2FA no banco. Mínimo de 32 caracteres. Trocar invalida sessões e 2FA ativos. |
| `LEGIVEL_ENCRYPTION_ENABLED` | `true` | não | não | Criptografa imagens com AES-256-GCM. Desligado, grava sem criptografia; arquivos antigos criptografados continuam legíveis se a chave estiver definida. |
| `LEGIVEL_ENCRYPTION_KEY` | — | com criptografia | não | Chave de 32 bytes em base64 (`python -m legivel.cli generate-key`). Cifra as imagens e os campos CPF, RG, CNH, MRZ, texto do OCR e dados extraídos. Sem ela nada disso pode ser lido. |
| `LEGIVEL_ENCRYPTION_OLD_KEYS` | vazio | não | não | Chaves anteriores, separadas por vírgula. Servem só para ler dados e arquivos ainda não recifrados. Ver *Rotação de chave* em [seguranca.md](seguranca.md). |
| `LEGIVEL_DATABASE_URL` | `sqlite:///./data/legivel.db` | não | não | `sqlite:///caminho.db` ou `postgresql://usuario:senha@host:5432/banco`. No Compose é montada a partir de `POSTGRES_*`. |
| `LEGIVEL_DATABASE_PASSWORD` | vazio | não | não | Senha do PostgreSQL, quando ela não está na URL. Substitui a senha da URL. No Compose vem de `secrets/database_app_password`. |
| `LEGIVEL_STORAGE_DIR` | `./storage` | não | não | Pasta das imagens. No Compose, volume `storage` em `/data/storage`. |
| `LEGIVEL_PUBLIC_URL` | vazio | não | não | Base dos links enviados por e-mail. Vazio usa o endereço da requisição. |

## E-mail

| Variável | Padrão | Obrigatória | Em execução | Descrição |
| --- | --- | --- | --- | --- |
| `LEGIVEL_SMTP_HOST` | vazio | não | não | Servidor SMTP. Vazio desliga o envio: convites e links de redefinição aparecem para o administrador copiar. |
| `LEGIVEL_SMTP_PORT` | `587` | não | não | Porta do SMTP. |
| `LEGIVEL_SMTP_SECURITY` | `starttls` | não | não | `starttls`, `ssl` ou `none`. |
| `LEGIVEL_SMTP_USER` / `LEGIVEL_SMTP_PASSWORD` | vazio | não | não | Credenciais, se o servidor exigir. |
| `LEGIVEL_SMTP_FROM` | — | com SMTP | não | Remetente das mensagens. |

Para desenvolvimento, `docker compose --profile dev up -d mailpit` sobe o [Mailpit](https://mailpit.axllent.org/) em `http://127.0.0.1:8026`. Com a API no Docker, use `LEGIVEL_SMTP_HOST=mailpit` e `LEGIVEL_SMTP_PORT=1025`; com a API fora do Docker, `LEGIVEL_SMTP_HOST=127.0.0.1` e `LEGIVEL_SMTP_PORT=1026`. Nos dois casos, `LEGIVEL_SMTP_SECURITY=none`.

## OCR

| Variável | Padrão | Obrigatória | Em execução | Descrição |
| --- | --- | --- | --- | --- |
| `LEGIVEL_OCR_ENGINE` | `rapidocr` | não | não | `rapidocr` (ONNX) ou `tesseract`. O Tesseract também é usado se o RapidOCR não iniciar. |
| `LEGIVEL_OCR_DEVICE` | `auto` | não | sim | `auto`, `cpu` ou `gpu`. Ver [benchmarks.md](benchmarks.md). |
| `LEGIVEL_OCR_LANGUAGES` | `por` | não | não | Idiomas do Tesseract. O RapidOCR usa o modelo latino PP-OCRv5, que cobre português. |
| `LEGIVEL_OCR_MODEL_DIR` | `./models` | não | não | Onde ficam os modelos ONNX (`python -m legivel.cli download-models`). |
| `LEGIVEL_OCR_WARMUP` | `true` | não | não | Prepara o motor ao subir, para a primeira leitura não esperar. |
| `LEGIVEL_OCR_PASSES` | `3` | não | sim | Quantas vezes a imagem é lida, cada vez com um efeito (contraste e nitidez, preto e branco, escurecimento). As leituras extras só rodam se algum campo vier vazio, inválido ou com confiança abaixo de 90%; cada campo fica com o valor de maior confiança, e o CPF só é trocado por um que passe no dígito verificador. |
| `LEGIVEL_READING_LANGUAGES` | `pt,en,es` | não | sim | Idiomas que os módulos de livros, digitalização, finanças e cartões tentam reconhecer. Cada alfabeto (latino, cirílico, chinês, japonês, coreano, árabe, devanágari) usa um modelo próprio, carregado na primeira leitura. |
| `LEGIVEL_DEFAULT_READING_LANGUAGE` | `auto` | não | sim | Idioma usado quando o envio não escolhe um. Em `auto`, o idioma é detectado pelo texto lido. |
| `LEGIVEL_STORE_CARD_NUMBERS` | `false` | não | sim | Guarda o número completo do cartão, sempre cifrado. Só pode ser ligado com a criptografia ativada; o CVV nunca é guardado. |

## Envio, imagens e retenção

| Variável | Padrão | Obrigatória | Em execução | Descrição |
| --- | --- | --- | --- | --- |
| `LEGIVEL_UPLOAD_MAX_MB` | `15` | não | sim | Limite por imagem, de 1 a 100 MB. |
| `LEGIVEL_UPLOAD_FORMATS` | `jpeg,png,webp,heic` | não | sim | Formatos aceitos. O formato é detectado pelo conteúdo, não pela extensão. |
| `LEGIVEL_IMAGE_QUALITY` | `88` | não | sim | Qualidade JPEG das imagens processadas, recortes e originais recomprimidos. |
| `LEGIVEL_COMPRESS_ORIGINALS` | `false` | não | sim | Regrava o original em JPEG, sem metadados, com no máximo `LEGIVEL_ORIGINAL_MAX_SIDE` pixels. |
| `LEGIVEL_ORIGINAL_MAX_SIDE` | `3000` | não | não | Maior lado do original recomprimido. |
| `LEGIVEL_RETENTION_DAYS` | `0` | não | sim | Apaga documentos e registros dos módulos com mais de N dias, com imagens e recortes. `0` mantém para sempre. |
| `LEGIVEL_RETENTION_INTERVAL_HOURS` | `24` | não | não | Intervalo da verificação de retenção. |
| `LEGIVEL_BACKGROUND_JOBS` | `true` | não | não | Liga a retenção automática e o preparo do OCR. |

## Contas e sessões

| Variável | Padrão | Obrigatória | Em execução | Descrição |
| --- | --- | --- | --- | --- |
| `LEGIVEL_PASSWORD_MIN_LENGTH` | `10` | não | sim | Tamanho mínimo da senha. |
| `LEGIVEL_PASSWORD_REQUIRE_MIXED` | `true` | não | sim | Exige letras com números ou símbolos. A senha nunca pode conter o e-mail nem estar entre as 10 mil senhas mais vazadas (lista do SecLists, consultada localmente). |
| `LEGIVEL_ARGON2_TIME_COST`, `LEGIVEL_ARGON2_MEMORY_KIB`, `LEGIVEL_ARGON2_PARALLELISM` | `3`, `65536`, `4` | não | não | Custo do hash Argon2id das senhas. O mínimo de memória segue a recomendação da OWASP (19 MiB). Ao mudar, cada senha é recalculada no próximo login. Cada login usa essa memória por alguns instantes; considere isso no limite de memória do container. |
| `LEGIVEL_LOGIN_MAX_ATTEMPTS` | `5` | não | sim | Erros seguidos que bloqueiam a conta. Além disso, cada IP tem limite de 20 tentativas em 5 minutos. |
| `LEGIVEL_LOGIN_LOCK_MINUTES` | `15` | não | sim | Duração do bloqueio. Um administrador pode desbloquear antes. |
| `LEGIVEL_ACCESS_MINUTES` | `15` | não | não | Validade do cookie de acesso. |
| `LEGIVEL_REFRESH_DAYS` | `30` | não | sim | Duração máxima de uma sessão desde o login. Renovar o acesso não estende esse prazo. |
| `LEGIVEL_SESSION_IDLE_HOURS` | `12` | não | sim | Sessão sem nenhuma renovação por mais que isto exige novo login. |
| `LEGIVEL_INVITE_HOURS` | `72` | não | sim | Validade do convite. |
| `LEGIVEL_RESET_MINUTES` | `60` | não | não | Validade do link de redefinição de senha. |
| `LEGIVEL_VERIFY_HOURS` | `48` | não | não | Validade do link de confirmação de e-mail. |
| `LEGIVEL_SCAN_LINK_HOURS` | `48` | não | sim | Validade padrão do link de envio remoto. |
| `LEGIVEL_SECURE_COOKIES` | `false` | não | não | Marca os cookies como `Secure`. Ligue quando houver HTTPS. |
| `LEGIVEL_PRODUCTION` | `false` | não | não | Modo produção. A API recusa subir sem `LEGIVEL_SECURE_COOKIES=true`, `LEGIVEL_PUBLIC_URL` com `https://`, criptografia ligada e, com SMTP, `LEGIVEL_SMTP_SECURITY` diferente de `none`. Ligue em toda instalação exposta na internet. |

## Instância e interface

| Variável | Padrão | Obrigatória | Em execução | Descrição |
| --- | --- | --- | --- | --- |
| `LEGIVEL_INSTANCE_NAME` | `Legível` | não | sim | Nome no menu, no login e nos e-mails. O logotipo é enviado pela tela de Configurações. |
| `LEGIVEL_DEFAULT_THEME` | `system` | não | sim | Tema para quem ainda não escolheu: `system`, `light` ou `dark`. |
| `LEGIVEL_DEFAULT_LANGUAGE` | `pt-BR` | não | sim | Idioma padrão da interface e dos e-mails: `pt-BR` ou `en`. Cada pessoa pode trocar em *Minha conta*. |
| `LEGIVEL_TIMEZONE` | `America/Sao_Paulo` | não | sim | Fuso das datas exibidas e da auditoria. |

## Papéis e permissões

Há três papéis: administrador, revisor e leitor. O administrador tem tudo e é o único que gerencia usuários e configurações. As permissões de revisor e leitor são editadas em *Configurações > Permissões por papel*; o padrão é:

| Permissão | Revisor | Leitor |
| --- | --- | --- |
| Consultar pessoas e documentos | sim | sim |
| Enviar documentos | sim | não |
| Revisar e reprocessar | sim | não |
| Apagar documentos | sim | não |
| Ver imagens originais | sim | não |
| Editar e verificar pessoas | sim | não |
| Apagar pessoas | não | não |
| Gerar links de envio | sim | não |
| Ver auditoria | não | não |

A API confere a permissão em cada rota; a interface só esconde o que o papel não pode usar.

## Interface web

| Variável | Padrão | Obrigatória | Descrição |
| --- | --- | --- | --- |
| `LEGIVEL_API_URL` | `http://127.0.0.1:8001` | não | Endereço interno da API. O Next encaminha `/api/*` para ele (rewrites), então o navegador só fala com a origem da interface e não há CORS. É lido no `next build` e na execução; no Compose vale `http://api:8000`. |

## Docker Compose

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `LEGIVEL_BIND` | `127.0.0.1` | Interface de rede em que a porta da interface é publicada. `0.0.0.0` libera para a rede local. |
| `LEGIVEL_PORT` | `8091` | Porta da interface no host. A API, o PostgreSQL e o Mailpit não são publicados, exceto o painel do Mailpit em `127.0.0.1`. |
| `POSTGRES_DB`, `POSTGRES_USER` | `legivel`, `legivel` | Banco e dono criados no primeiro `up`. A senha do dono fica em `secrets/postgres_password`. |
| `POSTGRES_APP_USER` | `legivel_app` | Usuário sem privilégios com que a API acessa o banco. Senha em `secrets/database_app_password`. |
| `LEGIVEL_API_MEMORY_LIMIT`, `LEGIVEL_WEB_MEMORY_LIMIT`, `POSTGRES_MEMORY_LIMIT` | `3g`, `512m`, `1g` | Limite de memória de cada container. |
| `MAILPIT_PORT` | `8026` | Porta do painel do Mailpit. |

### Segredos

O Compose não lê segredos do `.env`. Eles ficam em arquivos na pasta `secrets/`, montados só nos containers que precisam deles, em `/run/secrets`:

| Arquivo | Usado por | Conteúdo |
| --- | --- | --- |
| `postgres_password` | postgres, migrate | Senha do dono do banco. Só o serviço `migrate` a usa, para aplicar as migrações. |
| `database_app_password` | migrate, api | Senha do usuário `POSTGRES_APP_USER`, com que a API roda. |
| `secret_key` | migrate, api | `LEGIVEL_SECRET_KEY`. |
| `encryption_key` | migrate, api | `LEGIVEL_ENCRYPTION_KEY`. |
| `backup_passphrase` | `scripts/backup.sh` | Senha que cifra os backups. Não é montada em nenhum container. |

`scripts/gerar-segredos.sh` (ou `scripts\gerar-segredos.ps1` no Windows) cria os arquivos que faltam. Se o `.env` já tiver `POSTGRES_PASSWORD`, `LEGIVEL_SECRET_KEY` ou `LEGIVEL_ENCRYPTION_KEY`, o valor é copiado, então uma instalação existente continua lendo os mesmos dados; depois apague esses valores do `.env`. Arquivo que já existe nunca é sobrescrito.

A cada `up`, o serviço `migrate` aplica as migrações com o dono do banco, cria ou atualiza o usuário da aplicação e termina. A API só sobe depois dele. O usuário da aplicação lê e grava as tabelas, mas não altera o esquema, não apaga nem muda a auditoria e não mexe na versão das migrações.

### Isolamento dos containers

Todos os serviços rodam com o sistema de arquivos somente leitura (gravação só no volume de dados e em `/tmp` na memória), sem capacidades do Linux (o PostgreSQL mantém só as que precisa para trocar de usuário ao iniciar), com `no-new-privileges` e com limite de memória e de processos.

