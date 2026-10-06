# Novidades da versão 0.2.0

## Fotografar e conferir

Em **Novo documento** ou **Leitura**, a câmera guiada abre uma prévia com um enquadramento de referência. Depois da captura, o servidor identifica as bordas e estima desfoque, iluminação e reflexo antes do envio. Os avisos são orientações, não uma garantia de legibilidade. A análise não guarda a imagem.

A câmera no navegador exige HTTPS ou localhost. Em um endereço HTTP na rede local, use **Tirar foto** para abrir a câmera do aparelho. Os links de envio remoto também oferecem a análise, enquanto estiverem ativos.

## Revisar

Ao focar um campo, a revisão mostra o trecho correspondente da imagem tratada, com zoom. **Próximo campo a conferir** percorre os campos vazios, com problemas de validação ou confiança abaixo de 90%. Os atalhos são **Alt + N** para avançar e **Ctrl + Enter** para salvar.

Os recortes usam as coordenadas guardadas na leitura. Documentos de versões anteriores precisam ser reprocessados para ter essas coordenadas. Quando não há uma localização confiável, a tela pede para conferir a imagem completa.

## Fila

Com a criptografia ligada, documentos e módulos de livros, digitalização e finanças são enviados para a fila. A tela mostra progresso por página e o resultado de cada tarefa. Fechar o navegador não interrompe a leitura. Após reiniciar a API, tarefas interrompidas voltam à fila; a leitura da tarefa começa novamente, preservando um único resultado publicado.

O cancelamento é verificado entre páginas e antes de salvar o resultado. Uma leitura de OCR em andamento termina antes de obedecer ao cancelamento. Só tarefas que falharam podem ser repetidas. As imagens temporárias são cifradas e removidas após conclusão ou cancelamento; em caso de falha, permanecem para permitir nova tentativa.

**Selecionar várias imagens** envia até 50 documentos separados. O lote é apropriado para arquivos de uma página. Para frente e verso, use o envio individual; para um livro com várias páginas, use **Leitura**. A fila permite até 500 tarefas pendentes por usuário.

Cartões continuam sendo processados diretamente, sem guardar fotos na fila. Com a criptografia desligada, os envios individuais também usam o processamento direto. A fila exige uma única instância da API, sem vários workers ou réplicas simultâneas. `LEGIVEL_BACKGROUND_JOBS=false` desliga seu processamento automático.

## Duplicados

Ao reenviar um documento já processado, o sistema compara os hashes dos arquivos. O aviso permite abrir o existente, manter uma cópia ou substituí-lo. A substituição exige permissão de exclusão e só remove o registro anterior após a leitura nova terminar com sucesso. Documentos do mesmo tipo vinculados à mesma pessoa aparecem como possíveis semelhantes na revisão.

A comparação exata não identifica uma nova fotografia do mesmo papel como arquivo idêntico. Originais comprimidos pela versão 0.1.0 podem não ter um hash correspondente ao arquivo recebido; reenvios novos já guardam esse hash corretamente.

## Organização

A revisão de documentos e registros permite salvar pasta e etiquetas. A tela **Organizar** reúne os itens marcados e filtra por pasta e etiqueta. Essas marcações são pessoais e não alteram as permissões de acesso ao documento.

Em Pessoas, Documentos, Registros, Busca e Organizar, **Buscas salvas** guarda o endereço atual com os filtros. As buscas ficam no banco, vinculadas à conta, e podem ser removidas.

## Cópias com ocultação

Na revisão, abra **Exportar com ocultação**. Selecione dois cantos na imagem para cobrir uma área ou informe as coordenadas percentuais pelo teclado. É possível selecionar várias áreas e páginas, incluindo nomes, números, assinaturas ou fotos.

Confira a prévia de todas as páginas para liberar o download. As áreas são pintadas nos pixels antes de criar o PDF. O arquivo exportado contém apenas as imagens resultantes, sem camada de texto pesquisável, imagens originais anexadas ou metadados do documento de origem. A ocultação é manual: confira se todas as ocorrências do dado estão cobertas. O documento armazenado permanece disponível para revisão.

## Assistente de instalação

Requisitos: Python 3 e Docker com Compose funcionando.

```powershell
python scripts/instalar.py
```

No Windows também pode usar `powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1`; no Linux, `sh scripts/instalar.sh`.

O assistente pede a porta na primeira instalação, prepara `.env` e os arquivos de segredos, inicia os serviços e confere configuração, banco, OCR e interface. Configurações e chaves existentes são preservadas. O primeiro build pode demorar.

- `--yes`: usa os padrões sem perguntas.
- `--port 8099`: escolhe a porta de uma instalação nova.
- `--check-only`: confere Docker e Compose sem alterar arquivos.
- `--no-start`: prepara a configuração sem iniciar serviços.

A conta de administrador é criada na primeira visita à interface. Para atualizar uma instalação, faça backup do banco, das imagens e das chaves e execute novamente o assistente ou `docker compose up -d --build`. O serviço de migração cria as tabelas da versão 0.2.0 antes de iniciar a API. Não execute um downgrade do banco para a versão 0.1.0 sem restaurar um backup correspondente.
