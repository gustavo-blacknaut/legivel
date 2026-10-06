"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { PageHead } from "@/components/PageHead";
import { Forbidden } from "@/components/Forbidden";
import page from "@/components/Page.module.css";
import { useSession } from "@/lib/session";
import { useWords } from "@/lib/maintenance-text";
import { workflowJson } from "@/lib/workflow";
import { startBatch, type ReviewItem } from "@/lib/batch-review";

export default function BatchReviewPage() {
  const words = useWords();
  const { can } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const [entity, setEntity] = useState("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState("");
  const queue = useQuery({ queryKey: ["review-queue", entity], queryFn: () => workflowJson<{ items: ReviewItem[]; total: number }>(`/api/review/queue?entity=${entity}&limit=200`), enabled: can("documents.review") });
  if (!can("documents.review")) return <Forbidden />;
  const items = queue.data?.items ?? [];
  const keyOf = (item: ReviewItem) => `${item.entity}:${item.id}`;
  const begin = () => {
    const chosen = items.filter((item) => selected.includes(keyOf(item)));
    if (!chosen.length) return;
    try { router.push(startBatch(chosen)); }
    catch { setError(words("O navegador não permitiu guardar a sessão de revisão.", "The browser could not store the review session.")); }
  };
  return <div className={page.page}>
    <PageHead title={words("Revisão em lote", "Batch review")} description={words("Selecione os itens pendentes. Confira, salve e avance sem voltar à lista.", "Select pending items. Review, save and continue without returning to the list.")} />
    {params.has("finished") && <p className="alert alert-success" role="status">{words(`Lote encerrado: ${Number(params.get("finished")) || 0} de ${Number(params.get("total")) || 0} itens confirmados. Itens pulados continuam pendentes.`, `Batch finished: ${Number(params.get("finished")) || 0} of ${Number(params.get("total")) || 0} items confirmed. Skipped items remain pending.`)}</p>}
    <section className="panel panel-body workflow-stack">
      <label className="field">{words("Tipo de item", "Item type")}<select value={entity} onChange={(event) => { setEntity(event.target.value); setSelected([]); }}><option value="all">{words("Todos", "All")}</option><option value="document">{words("Identidades", "Identities")}</option><option value="record">{words("Leituras", "Readings")}</option></select></label>
      <div className="workflow-row">
        <button className="button button-secondary" type="button" onClick={() => setSelected(items.map(keyOf))}>{words("Selecionar todos da lista", "Select all listed")}</button>
        <button className="button button-secondary" type="button" onClick={() => setSelected([])}>{words("Limpar seleção", "Clear selection")}</button>
        <button className="button" type="button" onClick={begin} disabled={!selected.length || queue.isFetching}>{words(`Iniciar revisão (${selected.length})`, `Start review (${selected.length})`)}</button>
      </div>
      <p>{words(`${queue.data?.total ?? 0} itens pendentes. A lista mostra até 200, dos mais antigos aos mais recentes.`, `${queue.data?.total ?? 0} pending items. Up to 200 are shown, oldest first.`)}</p>
      {(error || queue.error) && <p role="alert">{error || queue.error?.message}</p>}
      {queue.isLoading && <p role="status">{words("Carregando…", "Loading…")}</p>}
      {!queue.isLoading && !items.length && <p>{words("Nenhum item pendente.", "No pending items.")}</p>}
      {items.map((item) => <label className="workflow-item workflow-row" key={keyOf(item)}><input type="checkbox" checked={selected.includes(keyOf(item))} onChange={(event) => setSelected((current) => event.target.checked ? [...current, keyOf(item)] : current.filter((key) => key !== keyOf(item)))} /><span>{item.entity === "document" ? words("Identidade", "Identity") : words("Leitura", "Reading")} #{item.id} · {item.title}</span></label>)}
    </section>
  </div>;
}
