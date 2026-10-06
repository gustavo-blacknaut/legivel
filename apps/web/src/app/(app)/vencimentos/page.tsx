"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { useWords } from "@/lib/maintenance-text";
import { workflowJson } from "@/lib/workflow";

export type Expirations = { today: string; days: number; overdue: number; due: number; total: number; filtered_total: number; page_size: number; items: { entity: "document" | "record"; id: number; title: string; date: string; days_left: number }[] };
export default function ExpirationsPage() {
  const words = useWords();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const alerts = useQuery({ queryKey: ["expirations", filter, currentPage], queryFn: () => workflowJson<Expirations>(`/api/expirations?status=${filter}&page=${currentPage}`), refetchInterval: 60_000 });
  const setDays = async (days: number) => {
    setBusy(true); setError("");
    try { await workflowJson("/api/expirations/preferences", "PUT", { days }); setCurrentPage(1); await client.invalidateQueries({ queryKey: ["expirations"] }); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Erro"); }
    finally { setBusy(false); }
  };
  const items = alerts.data?.items ?? [];
  return <div className={page.page}>
    <PageHead title={words("Vencimentos", "Expiry alerts")} description={words("Acompanhe identidades, contratos, cartões e vencimentos financeiros.", "Track identity documents, contracts, cards and financial due dates.")} />
    <section className="panel panel-body workflow-stack">
      <div className="workflow-row"><label className="field">{words("Avisar com antecedência", "Notify in advance")}<select value={alerts.data?.days ?? 30} disabled={busy || !alerts.data} onChange={(event) => void setDays(Number(event.target.value))}>{[7, 30, 60, 90].map((days) => <option key={days} value={days}>{words(`${days} dias`, `${days} days`)}</option>)}</select></label><label className="field">{words("Mostrar", "Show")}<select value={filter} onChange={(event) => { setFilter(event.target.value); setCurrentPage(1); }}><option value="all">{words("Todos", "All")}</option><option value="overdue">{words("Vencidos", "Expired")}</option><option value="due">{words("Próximos do vencimento", "Due soon")}</option></select></label></div>
      <p role="status">{words(`${alerts.data?.overdue ?? 0} vencidos · ${alerts.data?.due ?? 0} próximos do vencimento`, `${alerts.data?.overdue ?? 0} expired · ${alerts.data?.due ?? 0} due soon`)}</p>
      <p>{words("Os alertas aparecem neste painel e no menu. Confira as datas extraídas durante a revisão; documentos sem validade preenchida não entram na lista.", "Alerts appear on this panel and in the menu. Check extracted dates during review; documents without an expiry date are not listed.")}</p>
      {(error || alerts.error) && <p role="alert">{error || alerts.error?.message}</p>}
      {alerts.isLoading && <p role="status">{words("Carregando…", "Loading…")}</p>}
      {!alerts.isLoading && !items.length && <p>{words("Nenhum vencimento neste período.", "No expiry dates in this period.")}</p>}
      {items.map((item) => <article className="workflow-item" key={`${item.entity}:${item.id}`}><Link className="workflow-link" href={`/${item.entity === "document" ? "documentos" : "registros"}/${item.id}`}>{item.title} · #{item.id}</Link><span><time dateTime={item.date}>{item.date.split("-").reverse().join("/")}</time> · {item.days_left < 0 ? words(`Vencido há ${-item.days_left} dias`, `Expired ${-item.days_left} days ago`) : item.days_left === 0 ? words("Vence hoje", "Expires today") : words(`Vence em ${item.days_left} dias`, `Expires in ${item.days_left} days`)}</span></article>)}
      <div className="workflow-row"><button className="button button-secondary" type="button" disabled={currentPage === 1 || alerts.isFetching} onClick={() => setCurrentPage((value) => value - 1)}>{words("Anterior", "Previous")}</button><span>{words(`Página ${currentPage}`, `Page ${currentPage}`)}</span><button className="button button-secondary" type="button" disabled={alerts.isFetching || currentPage * (alerts.data?.page_size ?? 50) >= (alerts.data?.filtered_total ?? 0)} onClick={() => setCurrentPage((value) => value + 1)}>{words("Próxima", "Next")}</button></div>
    </section>
  </div>;
}
