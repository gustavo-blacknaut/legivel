# Roteiro de teste com celulares reais

Use dados fictícios e uma instalação de teste do Legível acessível por HTTPS. A câmera guiada depende de um contexto seguro e da permissão de câmera do navegador. Use uma identidade ou formulário fictício impresso, com texto pequeno e uma data de validade conhecida.

O roteiro abaixo está preparado para execução. Resultados de sensores físicos só devem ser registrados depois do teste no aparelho.

## Matriz

| Aparelho | Navegador | Versão do sistema | Resultado físico |
| --- | --- | --- | --- |
| Android com câmera traseira | Chrome | Preencher no teste | Pendente |
| iPhone com câmera traseira | Safari | Preencher no teste | Pendente |

Para a automação de compatibilidade, execute em `apps/web`:

```sh
npx playwright install chromium webkit
npx playwright test --project=mobile-chrome --project=mobile-safari
```

Esses perfis emulados verificam comportamento de navegador e layout. Eles não medem foco, nitidez ou captura do sensor físico.

## Passos no aparelho

1. Abra `/novo` por HTTPS. Confira que frente e verso, escolha de arquivo e câmera nativa estão disponíveis. Recuse a câmera guiada e confirme que é possível usar a câmera nativa. Depois conceda a permissão e reabra a captura.
2. Capture com a câmera traseira, primeiro em retrato e depois em paisagem. Verifique enquadramento, orientação, foco, texto pequeno e as bordas indicadas após a captura. Faça outra foto com pouca luz e confira os avisos de qualidade.
3. Quando disponíveis, teste câmera frontal/traseira, luz e zoom. Feche e abra o painel, troque de câmera e coloque o navegador em segundo plano. Confira que o indicador do sistema de uso da câmera é encerrado.
4. Substitua a foto e remova a seleção. Envie um documento fictício, acompanhe a fila e compare original e tratada. Amplie para conferir caracteres pequenos, data e perspectiva. Confira se a captura nativa preserva a orientação das fotos.
5. Revise os campos com o teclado aberto. Inicie um lote de dois itens, altere um campo, teste a confirmação ao pular e use **Salvar e próximo**. Confira que o teclado e os botões não escondem o conteúdo.
6. Aplique um modelo em uma digitalização, preencha uma data de validade e confirme sua presença em **Vencimentos**. Abra a comparação em retrato e paisagem e confira que a página não rola horizontalmente.

## Registro

Anote data, modelo do aparelho, versão do sistema e navegador, versão do Legível, orientações usadas, iluminação, recursos de câmera disponíveis e o resultado de cada passo. Se houver falha, registre o passo e uma captura de tela sem dados pessoais. Não marque como aprovado um recurso que o aparelho não oferece; registre **não disponível** para luz, zoom ou seleção de câmera quando for o caso.
