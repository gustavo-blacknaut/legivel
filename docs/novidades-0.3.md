# Legível 0.3.0

Esta versão acrescenta recuperação pelo painel, histórico de revisão, importação de PDF, exportação em lote e manutenção.

## Backup e recuperação

Administradores encontram **Manutenção e backups** no menu. Defina uma senha de pelo menos 12 caracteres e clique em **Criar e baixar backup**. O arquivo `.lgb` usa AES-GCM e uma chave derivada da senha com PBKDF2. Ele contém o banco, os arquivos armazenados, as configurações do painel e as chaves da instalação. Guarde a senha separada do arquivo. Variáveis de ambiente e arquivos de implantação do servidor continuam sob sua responsabilidade.

Para conferir um backup, escolha o arquivo, informe a senha e clique em **Testar recuperação**. O servidor importa os dados em um SQLite temporário, verifica relações e integridade, e confere a descriptografia das imagens e dos campos protegidos. O teste não substitui os dados em uso.

Para restaurar, baixe primeiro um backup atual. Depois de testar o arquivo desejado, clique em **Preparar restauração**, leia a confirmação e digite `RESTAURAR`. Novas gravações, a fila e a retenção ficam pausadas. Reinicie a API no servidor:

```sh
docker compose restart api
```

A restauração é aplicada antes de iniciar os serviços. Banco e imagens voltam ao estado do backup. Alterações posteriores serão perdidas, todas as sessões serão encerradas e um evento de restauração será registrado. Entre novamente com uma conta existente no backup. Antes do reinício, **Cancelar restauração** remove a preparação e libera as gravações.

Use a mesma versão do schema e as mesmas chaves do backup. Em outro servidor, recupere as chaves em uma pasta vazia, sem imprimi-las no terminal:

```sh
cd apps/api
uv run python -m legivel.services.backups /caminho/backup.lgb --output /caminho/chaves-recuperadas
```

O comando pede a senha e grava `secret_key.txt`, `encryption_key.txt` e, quando necessário, `encryption_old_keys.txt`. Configure os arquivos nas variáveis `LEGIVEL_SECRET_KEY_FILE`, `LEGIVEL_ENCRYPTION_KEY_FILE` e `LEGIVEL_ENCRYPTION_OLD_KEYS_FILE`. Não substitua chaves de um servidor com dados sem um plano de recuperação.

O painel aceita backups de até 200 MB. Para instalações maiores, continuam disponíveis `scripts/backup.sh` e `scripts/restaurar-backup.sh`. Esses scripts usam seu próprio formato e devem seguir a documentação de implantação. Mantenha uma única instância da API ao preparar e aplicar uma restauração.

## Histórico de revisão

Documentos e leituras registram alterações futuras, autor, data e os valores anteriores e novos. O conteúdo do histórico é criptografado. Quem tem acesso aos dados completos pode consultá-lo; desfazer também exige permissão de revisão.

**Desfazer última revisão** restaura os campos anteriores e cria outra entrada no histórico. Se os dados mudarem antes da confirmação, o servidor recusa a operação e pede atualização. Alterações feitas antes da 0.3.0 não são reconstruídas. Excluir um documento também remove seu histórico de campos, mantendo os eventos de auditoria.

## Importação de PDF

Em **Importar PDF**, envie um arquivo, informe a senha se necessário, escolha as páginas, ajuste a rotação e confira as prévias. É possível enviar as páginas para livros e textos, scanner ou identidade com frente e verso.

Limites: 100 MB por PDF, 100 páginas por arquivo e até 50 páginas por envio. Identidades aceitam no máximo duas páginas. As páginas escolhidas são rasterizadas para leitura e guardadas como imagens; o PDF original permanece com o usuário. Prévia e importação respeitam a ordem selecionada. PDFs inválidos, senhas incorretas e seleções fora dos limites são recusados.

## Melhoria das imagens

O preparo anterior já corrigia perspectiva, orientação e contraste. Agora também corrige pequenas inclinações quando encontra linhas suficientes com ângulos consistentes. Imagens sem evidência suficiente ficam sem essa correção. O OCR ainda confere a orientação do texto. As melhorias afetam a imagem processada; o original é preservado conforme a política de armazenamento configurada. A opção existente de comprimir originais continua valendo quando habilitada.

## Exportação em lote

Em **Exportar em lote**, selecione até 100 documentos ou leituras, inclusive de páginas diferentes. Baixe CSV com separador `;`, Excel ou ZIP. CSV e Excel protegem valores que poderiam ser interpretados como fórmulas. O ZIP contém um JSON com os dados e as imagens originais disponíveis. Cada exportação é registrada na auditoria.

O lote exige permissão para revelar dados. O ZIP também exige acesso aos originais. Números completos de cartão não entram no lote. A ocultação manual continua na exportação individual; o ZIP contém originais. O limite de resposta é 200 MB; reduza a seleção se necessário.

## Acessibilidade

Há um link **Ir para o conteúdo**, um marco de conteúdo principal, foco contido no menu móvel e no visualizador de imagens, retorno de foco ao fechar e mensagens de progresso e erro anunciadas. Os novos controles têm rótulos e suportam teclado. A suíte de navegador verifica regras WCAG A/AA com axe, além de responsividade e tamanho dos alvos de toque. Verificações automáticas não substituem testes com usuários de leitores de tela.

## Manutenção

O painel mostra o banco, o motor configurado, espaço usado e livre, falhas na fila, arquivos ausentes e o estado dos backups. **Limpar arquivos temporários** remove somente arquivos das categorias de armazenamento que não têm referência no banco e têm mais de 24 horas. Imagens de documentos, identidade visual e arquivos de tarefas, inclusive tarefas com falha, são preservados. A limpeza exige confirmação e fica registrada na auditoria.

## Atualização

Faça backup antes de atualizar. A versão inclui a migração `0011`, com a tabela do histórico. No Docker, a migração é executada pelo serviço de migração:

```sh
docker compose up -d --build
```

Uma restauração preparada deve ser aplicada ou cancelada antes de trocar de versão. Não restaure um backup com outro schema. Preserve banco, armazenamento, `.env` e `secrets` ao atualizar.
