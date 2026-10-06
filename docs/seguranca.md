# Segurança

## O que é sensível

- Imagens de documentos (originais, processadas, miniaturas e recortes de foto, assinatura e polegar).
- CPF, número do RG, registro da CNH, nomes, filiação, datas e naturalidade.
- Texto bruto do OCR, que repete tudo isso.
- Senhas, segredos de 2FA, tokens de sessão, convite, redefinição e envio remoto.

## Base legal e finalidade

O Legível é uma ferramenta; quem a instala é o controlador. O uso previsto é cadastro de pessoas a partir dos próprios documentos delas, por exemplo em admissão de funcionários, com base no art. 7º, II (obrigação legal) ou V (execução de contrato) da LGPD. Quem operar o sistema deve registrar a base legal adotada, avisar o titular no momento da coleta e configurar a retenção de acordo.

Pedidos do titular: *Exportar dados*, na página da pessoa, baixa em JSON os dados consolidados, os campos e o texto de cada documento, os dados das imagens e o histórico de acessos ao cadastro (art. 18, II e V). *Apagar* remove a pessoa, os documentos e as imagens (art. 18, VI). As duas ações ficam na auditoria; exportar exige a permissão de ver dados completos.

## Quem pode atacar

| Atacante | O que tenta |
| --- | --- |
| Pessoa sem login | Adivinhar senhas, descobrir e-mails cadastrados, abusar do envio remoto, mandar arquivos maliciosos. |
| Usuário logado sem permissão | Ver ou alterar o que o papel dele não permite, acessando a API direto. |
| Convidado mal-intencionado | Reusar convite, escalar papel, ler dados de outros. |
| Quem obtém um backup ou o volume do Docker | Ler documentos e dados pessoais fora do sistema. |

Fora do escopo: comprometimento do sistema operacional do servidor, de quem tem a chave de criptografia e do próprio administrador.

## Achados da auditoria (04/10/2026)

| # | Gravidade | Onde | Risco | Correção |
| --- | --- | --- | --- | --- |
| 1 | Alta | `db/models.py` | CPF, RG, CNH, nomes e texto do OCR ficam em claro no banco: quem copia o backup ou o volume lê tudo. | Criptografar esses campos com AES-256-GCM e buscar CPF por HMAC (índice cego). |
| 2 | Alta | uvicorn | O log de acesso grava a URL inteira, com tokens de convite e de envio remoto. | Desligar o log de acesso do uvicorn. |
| 3 | Alta | `imaging/preprocess.py` | Imagem com dimensões enormes (decompression bomb) passa pela checagem e esgota a memória. | Limitar largura, altura e total de pixels antes de decodificar. |
| 4 | Alta | `main.py` | Não há limite de tamanho do corpo: o upload é lido inteiro antes da checagem de MB. | Recusar corpos acima do limite pelo `Content-Length` e durante a leitura. |
| 5 | Média | `auth/routes.py` | Login responde diferente para conta bloqueada (423) e desativada (403), o que revela que o e-mail existe. | Mesma resposta para todos os casos e bloqueio também por e-mail inexistente. |
| 6 | Média | `auth/routes.py` | Redefinição de senha envia o e-mail na mesma requisição: o tempo de resposta revela se a conta existe. | Enviar em segundo plano e responder sempre igual. |
| 7 | Média | `services/audit.py` | A auditoria guarda e-mails digitados em logins falhos e em convites. | Guardar só ids e e-mail mascarado. |
| 8 | Média | `auth/tokens.py` | A sessão renova sem limite: sem expiração absoluta nem por inatividade. | Expiração absoluta e por inatividade, configuráveis. |
| 9 | Média | `security/crypto.py` | Uma única chave, sem rotação. | Várias chaves com identificador e comando para recriptografar. |
| 10 | Média | API e interface | CPF aparece completo em listas e telas. | Mascarar por padrão e revelar com ação explícita, registrada na auditoria. |
| 11 | Média | `docker-compose.yml` | Containers com capacidades padrão, sem limite de memória, banco acessado pelo superusuário e segredos em variável de ambiente. | `cap_drop`, `no-new-privileges`, `read_only`, limites, usuário do banco sem privilégio e segredos por arquivo. |
| 12 | Média | `next.config.ts` | CSP com `unsafe-inline` nos scripts; falta HSTS e COOP. | CSP com nonce gerado no `proxy.ts`, HSTS e COOP. |
| 13 | Média | `auth/passwords.py` | Não há checagem contra senhas vazadas. | Lista local das senhas mais vazadas, sem consulta externa. |
| 14 | Média | LGPD | Não há exportação dos dados de uma pessoa. | Exportação em JSON, registrada na auditoria. |
| 15 | Média | `services/audit.py` | A auditoria pode ser alterada ou apagada direto no banco. | Gatilhos que bloqueiam UPDATE e DELETE. |
| 16 | Baixa | `auth/totp.py` | Códigos de recuperação com SHA-256 sem segredo. | HMAC com a chave do servidor. |
| 17 | Baixa | `auth/routes.py` | Falhas na confirmação de e-mail não contam para o limite por IP. | Registrar as falhas. |
| 18 | Baixa | `main.py` | Erros de validação devolvem o valor enviado. | Remover o valor das respostas 422. |
| 19 | Baixa | `web/routes.py` | Imagens sem `Content-Disposition`. | `inline` com nome gerado. |
| 20 | Baixa | `config.py` | Nada impede subir em produção com HTTP e cookie sem `Secure`. | Modo produção que recusa configuração insegura. |
| 21 | Baixa | `auth/passwords.py` | Parâmetros do Argon2 fixos. | Parâmetros configuráveis. |
| 22 | Baixa | CI | Sem varredura de segredos, de imagens e de código. | gitleaks, Trivy e CodeQL no CI, gitleaks no pre-commit. |
| 23 | Baixa | README | Backup sem criptografia. | Backup cifrado e restauração testada. |

Situação em 05/10/2026: os 23 achados foram corrigidos, cada um em um commit próprio. Pontos que dependem de quem instala: ligar `LEGIVEL_PRODUCTION=true` em instalação exposta, guardar `secrets/` fora do servidor e agendar `scripts/backup.sh`.

Itens conferidos sem problema: CSRF (cabeçalho obrigatório e SameSite=Strict), consultas só pelo ORM, paginação limitada a 100, tokens de convite e redefinição aleatórios, de uso único e guardados como hash, segredo do 2FA cifrado, permissões checadas no servidor em todas as rotas, retorno do login sem open redirect, nenhuma busca de URL externa (sem SSRF), nada sensível em `localStorage` ou em variáveis `NEXT_PUBLIC_`, imagens derivadas sem EXIF.

## Fora desta rodada

- Rodar o OCR em processo separado, com limite de memória e tempo próprios.
- Varredura dinâmica com OWASP ZAP.
- Alertas por e-mail para eventos suspeitos.
- SBOM nos releases.
