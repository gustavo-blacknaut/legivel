"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Forbidden } from "@/components/Forbidden";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { useWords } from "@/lib/maintenance-text";
import { useSession } from "@/lib/session";
import { saveBlob, workflowJson, workflowRequest } from "@/lib/workflow";

type Item = { id: number; full_name?: string; title?: string; doc_type?: string; module?: string; status: string };
export default function ExportPage() {
  const words = useWords();
  const { can } = useSession();
  const [entity, setEntity] = useState<"document" | "record">("document");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [format, setFormat] = useState("csv");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["export-list", entity, query, offset], queryFn: () => workflowJson<{ items: Item[]; total: number }>(`/api/${entity === "document" ? "documents" : "records"}?q=${encodeURIComponent(query)}&page=${offset}&page_size=50`), enabled: can("data.reveal") });
  if (!can("data.reveal")) return <Forbidden />;
  const download = async () => {
    setBusy(true); setError("");
    try {
      const response = await workflowRequest("/api/export/batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ entity, ids: selected, format }) });
      saveBlob(await response.blob(), `legivel-lote.${format}`);
    } catch (error) { setError(error instanceof Error ? error.message : "Erro"); }
    finally { setBusy(false); }
  };
  return <div className={page.page}>
    <PageHead title={words("Exportar em lote", "Batch export")} description={words("Selecione até 100 documentos e baixe os dados ou os arquivos originais.", "Select up to 100 documents and download their data or original files.")} />
    <section className="panel panel-body workflow-stack" aria-busy={busy}>
      <div className="workflow-row">
        <label className="field">{words("Conteúdo", "Content")}<select value={entity} disabled={busy} onChange={(event) => { setEntity(event.target.value as "document" | "record"); setSelected([]); setOffset(1); }}><option value="document">{words("Documentos", "Documents")}</option><option value="record">{words("Leituras", "Readings")}</option></select></label>
        <label className="field">{words("Buscar", "Search")}<input value={query} onChange={(event) => { setQuery(event.target.value); setOffset(1); }} /></label>
        <label className="field">{words("Formato", "Format")}<select value={format} disabled={busy} onChange={(event) => setFormat(event.target.value)}><option value="csv">CSV</option><option value="xlsx">Excel</option>{can("images.original") && <option value="zip">ZIP</option>}</select></label>
      </div>
      <p role="status">{selected.length} {words("selecionados", "selected")}</p>
      {error && <p role="alert">{error}</p>}{list.error && <p role="alert">{list.error.message}</p>}
      <div className="workflow-row"><button className="button button-secondary" type="button" disabled={busy} onClick={() => setSelected([...new Set([...selected, ...(list.data?.items.map((item) => item.id) ?? [])])].slice(0, 100))}>{words("Selecionar esta página", "Select this page")}</button><button className="button button-secondary" type="button" disabled={busy} onClick={() => setSelected([])}>{words("Limpar seleção", "Clear selection")}</button></div>
      {list.data?.items.map((item) => <div key={item.id} className="workflow-row workflow-item">
        <label className="check"><input type="checkbox" checked={selected.includes(item.id)} disabled={busy || (!selected.includes(item.id) && selected.length >= 100)} onChange={(event) => setSelected(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} />{item.full_name || item.title || `${words("Documento", "Document")} ${item.id}`}</label>
        <Link className="workflow-link" href={`/${entity === "document" ? "documentos" : "registros"}/${item.id}`}>{words("Abrir", "Open")}</Link>
      </div>)}
      <div className="workflow-row"><button className="button button-secondary" type="button" disabled={offset <= 1 || busy} onClick={() => setOffset(offset - 1)}>{words("Anterior", "Previous")}</button><span>{words("Página", "Page")} {offset}</span><button className="button button-secondary" type="button" disabled={busy || offset * 50 >= (list.data?.total ?? 0)} onClick={() => setOffset(offset + 1)}>{words("Próxima", "Next")}</button></div>
      <button className="button" type="button" disabled={busy || !selected.length} onClick={download}>{busy ? words("Exportando…", "Exporting…") : words("Baixar selecionados", "Download selection")}</button>
      <p className="muted">{words("O ZIP contém dados e imagens originais. A ocultação deve ser feita na exportação individual. Números completos de cartão ficam fora do lote.", "ZIP contains data and original images. Apply redactions through individual exports. Full card numbers are excluded from batch exports.")}</p>
    </section>
  </div>;
}
