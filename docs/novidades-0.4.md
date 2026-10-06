# Legível 0.4.0

## Comparação de imagens

Na revisão de identidades e leituras que guardam imagens, **Comparar original e tratada** abre duas imagens, com seleção de página e ampliação de até 300%. No celular, elas ficam uma abaixo da outra. Use as barras de rolagem ou o teclado para inspecionar detalhes. A comparação exige a permissão de acesso aos originais. Fechar com Escape devolve o foco ao botão.

A imagem original segue a política de armazenamento da instalação, incluindo a opção já existente de compressão. A comparação permite conferir perspectiva, orientação, contraste e perda de detalhes antes de confirmar os campos.

## Revisão em lote

Em **Revisão em lote**, escolha identidades, leituras ou ambas, selecione os itens e inicie. A lista mostra até 200 pendências, das mais antigas às mais recentes. **Salvar e próximo** salva a revisão usando as permissões e o histórico existentes e abre o próximo item. **Pular este item** avança sem confirmar a revisão. **Anterior** permite voltar. Se houver alterações não salvas, o painel pede confirmação antes de descartá-las.

O lote guarda apenas identificadores e progresso na sessão do navegador, sem campos ou nomes. Recarregar preserva essa sessão na mesma aba. Encerrar a aba encerra a sessão local; as revisões salvas permanecem no servidor. Se outro operador excluir um item, use a lista para iniciar um novo lote. Uma falha ao salvar mantém o usuário no item atual.

## Modelos de documentos

Administradores podem criar, editar e excluir modelos em **Modelos de documentos**. Cada modelo aceita até 30 campos de texto, texto longo ou data, com aviso de preenchimento obrigatório. Um campo de data pode representar a validade. Há um limite de 100 modelos na instalação.

Na revisão de uma digitalização ou de livros/textos, selecione o modelo e clique em **Aplicar modelo**. O texto extraído serve como referência para preencher os novos campos; a aplicação não faz extração automática desses campos. Identidades e cartões continuam com seus campos próprios. Salve alterações pendentes antes de aplicar o modelo.

Cada leitura mantém uma cópia dos campos do modelo, criptografada junto com seus dados. Editar ou excluir o modelo não muda leituras existentes. Uma leitura aceita um modelo, preservando os campos já aplicados. Alterações nos valores entram no histórico de revisão e na exportação em lote. O backup também inclui modelos e campos aplicados.

## Vencimentos

O menu **Vencimentos** mostra a quantidade de documentos vencidos ou próximos do vencimento. O painel inclui a validade das identidades, o vencimento de leituras financeiras, a validade dos cartões e o campo de validade dos modelos aplicados a leituras. Cartões vencem no último dia do mês informado. Escolha antecedência de 7, 30, 60 ou 90 dias; a preferência é individual e persiste no servidor. Filtre vencidos ou próximos do vencimento e navegue por páginas.

Os dias usam a data atual do fuso horário configurado na instalação. Uma validade igual à data atual aparece como **Vence hoje**; datas anteriores aparecem como vencidas. Confira as datas durante a revisão: campos vazios ou datas de modelo inválidas não geram alertas. Os alertas são atualizados ao abrir o aplicativo e a cada minuto enquanto ele está aberto. Eles ficam no painel e no menu.

## Captura e compatibilidade móvel

A câmera guiada aguarda o vídeo estar pronto antes de liberar a captura. Quando o navegador disponibiliza os controles, é possível escolher a câmera, usar a luz e ajustar o zoom. Trocar de câmera encerra o vídeo anterior. Fechar o painel ou colocar a página em segundo plano encerra os trilhos de vídeo. Se a câmera não abrir, há uma alternativa para usar a captura nativa do aparelho. Fotos guiadas são limitadas a 3000 pixels no maior lado para reduzir uso de memória.

A automação cobre Chromium com perfil Android e WebKit com perfil iPhone, retrato e paisagem, seleção de arquivo, remoção e comparação de imagens. A câmera guiada também tem testes com vídeo simulado, permissões recusadas e controles opcionais. Esses testes não são testes com sensores físicos. O roteiro em [testes-celulares.md](testes-celulares.md) permite concluir a validação em aparelhos reais.

## Atualização

Faça backup e atualize com `docker compose up -d --build`. O schema permanece na migração 0011. Os modelos e preferências usam as configurações existentes; os campos aplicados usam os dados criptografados das leituras. Para restaurar um backup, mantenha a versão correspondente do aplicativo e suas chaves.
