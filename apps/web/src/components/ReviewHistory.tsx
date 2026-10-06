"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSession } from "@/lib/session";
import { workflowJson } from "@/lib/workflow";
import { useWords } from "@/lib/maintenance-text";
import { Dialog } from "./Dialog";
import { useToast } from "./Toast";

type Revision = { id: number; author: string; created_at: string; changes: Record<string, { before: string; after: string }> };
export function ReviewHistory({ entity, id }: { entity: "document" | "record"; id: number }) {
  const { can } = useSession();
  const words = useWords();
  const toast = useToast();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState<Revision | null>(null);
  const [busy, setBusy] = useState(false);
  const revisions = useQuery({ queryKey: ["history", entity, id], queryFn: () => workflowJson<Revision[]>(`/api/history/${entity}/${id}`), enabled: open && can("data.reveal") });
  if (!can("data.reveal")) return null;
  const undo = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      const result = await workflowJson<{ detail: string }>(`/api/history/${entity}/${id}/${confirm.id}/undo`, "POST");
      toast(result.detail);
      await client.invalidateQueries({ queryKey: [entity, id] });
      await revisions.refetch();
      setConfirm(null);
    } catch (error) { toast(error instanceof Error ? error.message : "Erro", "error"); }
    finally { setBusy(false); }
  };
  return <section className="panel workflow-stack">
    <button className="button button-secondary" type="button" aria-expanded={open} onClick={() => { setOpen(!open); if (!open) void revisions.refetch(); }}>{words("Histórico de revisão", "Review history")}</button>
    {open && <div className="panel-body workflow-stack" aria-live="polite">
      {revisions.isFetching && <p role="status">{words("Carregando…", "Loading…")}</p>}
      {revisions.error && <p role="alert">{revisions.error.message}</p>}
      {revisions.data?.length === 0 && <p>{words("As próximas alterações aparecerão aqui.", "Future changes will appear here.")}</p>}
      {revisions.data?.map((revision, index) => <article className="workflow-item" key={revision.id}>
        <p><strong>{revision.author}</strong> · <time dateTime={revision.created_at}>{new Date(revision.created_at).toLocaleString()}</time></p>
        <dl className="workflow-stack">{Object.entries(revision.changes).map(([name, change]) => <div key={name}>
          <dt><strong>{name}</strong></dt><dd>{words("Antes", "Before")}: {change.before || "—"}<br />{words("Depois", "After")}: {change.after || "—"}</dd>
        </div>)}</dl>
        {index === 0 && can("documents.review") && <button className="button button-secondary" type="button" onClick={() => setConfirm(revision)}>{words("Desfazer última revisão", "Undo last review")}</button>}
      </article>)}
    </div>}
    <Dialog open={!!confirm} title={words("Desfazer revisão?", "Undo review?")} busy={busy} onClose={() => setConfirm(null)} actions={<>
      <button className="button button-secondary" type="button" disabled={busy} onClick={() => setConfirm(null)}>{words("Cancelar", "Cancel")}</button>
      <button className="button" type="button" disabled={busy} onClick={undo}>{words("Desfazer", "Undo")}</button></>}>
      <p>{words("Os campos voltarão aos valores anteriores. Essa ação também ficará registrada no histórico.", "Fields will return to their previous values. This action will also be recorded in the history.")}</p>
    </Dialog>
  </section>;
}
