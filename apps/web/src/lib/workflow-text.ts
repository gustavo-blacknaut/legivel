"use client";
import { useLocale } from "./i18n";
const pt = {
  queue: "Fila de processamento", queueDescription: "Os envios continuam mesmo ao fechar esta página. Tarefas interrompidas são retomadas após reiniciar o servidor.",
  organize: "Organizar", folder: "Pasta", tags: "Etiquetas (separadas por vírgula)", save: "Salvar", saved: "Salvo", empty: "Nenhum item encontrado.",
  cancel: "Cancelar", retry: "Tentar novamente", open: "Abrir", queued: "Na fila", running: "Processando", completed: "Concluído", failed: "Falhou", cancelled: "Cancelado", cancel_requested: "Cancelando",
  searches: "Buscas salvas", searchName: "Nome da busca", saveSearch: "Salvar busca atual", remove: "Remover", allFolders: "Todas as pastas", allTags: "Todas as etiquetas",
  hide: "Exportar com ocultação", hideHint: "Selecione dois cantos na imagem para cobrir uma área. Confira todas as páginas na prévia antes de baixar. O PDF exportado não terá texto pesquisável.",
  preview: "Conferir prévia", download: "Baixar PDF", clear: "Limpar áreas", page: "Página", original: "Selecionar áreas", noImages: "Sem imagens disponíveis.",
  region: "Área", reviewCrop: "Trecho do campo", noRegion: "Trecho não identificado. Confira a imagem completa.", nextIssue: "Próximo campo a conferir", shortcut: "Alt + N: próximo campo a conferir. Ctrl + Enter: salvar revisão.",
  similar: "Há outro documento deste tipo vinculado à mesma pessoa:", duplicate: "Este documento já existe", keep: "Manter nova cópia", link: "Abrir existente", replace: "Substituir existente", duplicateHint: "Confira o documento existente antes de decidir. Substituir remove o registro anterior após concluir a nova leitura.",
  capture: "Câmera guiada", captureHint: "Enquadre o documento inteiro, mantenha o celular firme e evite reflexos.", take: "Capturar", cameraUnavailable: "Câmera indisponível. Use a opção de foto do aparelho.",
  check: "Conferindo foto…", checked: "Foto conferida", qualityHint: "Os avisos são estimativas; confira a foto antes de enviar.", batch: "Selecionar várias imagens", batchHint: "Cada imagem será enviada como um documento separado.",
};
const en: typeof pt = {
  queue: "Processing queue", queueDescription: "Uploads continue when you close this page. Interrupted jobs resume after a server restart.",
  organize: "Organize", folder: "Folder", tags: "Tags (comma separated)", save: "Save", saved: "Saved", empty: "No items found.",
  cancel: "Cancel", retry: "Retry", open: "Open", queued: "Queued", running: "Processing", completed: "Completed", failed: "Failed", cancelled: "Cancelled", cancel_requested: "Cancelling",
  searches: "Saved searches", searchName: "Search name", saveSearch: "Save current search", remove: "Remove", allFolders: "All folders", allTags: "All tags",
  hide: "Export with redactions", hideHint: "Select two corners on the image to cover an area. Preview every page before downloading. The exported PDF will have no searchable text.",
  preview: "Preview", download: "Download PDF", clear: "Clear areas", page: "Page", original: "Select areas", noImages: "No images available.",
  region: "Area", reviewCrop: "Field image", noRegion: "Region not identified. Check the full image.", nextIssue: "Next field to check", shortcut: "Alt + N: next field to check. Ctrl + Enter: save review.",
  similar: "Another document of this type is linked to this person:", duplicate: "This document already exists", keep: "Keep new copy", link: "Open existing", replace: "Replace existing", duplicateHint: "Check the existing document before deciding. Replacement removes it after the new reading completes.",
  capture: "Guided camera", captureHint: "Frame the whole document, hold the phone steady and avoid glare.", take: "Capture", cameraUnavailable: "Camera unavailable. Use the device photo option.",
  check: "Checking photo…", checked: "Photo checked", qualityHint: "Warnings are estimates; check your photo before uploading.", batch: "Select multiple images", batchHint: "Each image will become a separate document.",
};
export function useWorkflowText() { return useLocale().language === "en" ? en : pt; }
