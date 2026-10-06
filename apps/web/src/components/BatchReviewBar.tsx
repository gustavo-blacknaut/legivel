"use client";
import { useState } from "react";
import { useWords } from "@/lib/maintenance-text";
import { useBatchReview } from "@/lib/batch-review";
import { Dialog } from "./Dialog";

export function BatchReviewBar({ batch, dirty, busy, onSave }: { batch: ReturnType<typeof useBatchReview>; dirty: boolean; busy: boolean; onSave: () => void }) {
  const words = useWords();
  const [offset, setOffset] = useState<number | null>(null);
  if (!batch.active) return null;
  const move = (direction: number) => dirty ? setOffset(direction) : batch.navigate(direction);
  return <section className="panel panel-body workflow-stack" aria-label={words("Revisão em lote", "Batch review")}>
    <p role="status">{words(`Revisão em lote · ${batch.index + 1} de ${batch.total} · ${batch.done} confirmados`, `Batch review · ${batch.index + 1} of ${batch.total} · ${batch.done} confirmed`)}</p>
    <div className="workflow-row">
      <button type="button" className="button button-secondary" disabled={busy || batch.index === 0} onClick={() => move(-1)}>{words("Anterior", "Previous")}</button>
      <button type="button" className="button button-secondary" disabled={busy} onClick={() => move(1)}>{words("Pular este item", "Skip this item")}</button>
      <button type="button" className="button" disabled={busy} onClick={onSave}>{words("Salvar e próximo", "Save and next")}</button>
    </div>
    <Dialog open={offset !== null} title={words("Descartar alterações não salvas?", "Discard unsaved changes?")} onClose={() => setOffset(null)} actions={<>
      <button className="button button-secondary" type="button" onClick={() => setOffset(null)}>{words("Continuar revisando", "Keep reviewing")}</button>
      <button className="button button-danger" type="button" onClick={() => { if (offset !== null) batch.navigate(offset); setOffset(null); }}>{words("Descartar e continuar", "Discard and continue")}</button>
    </>}><p>{words("As alterações deste formulário ainda não foram salvas.", "This form has unsaved changes.")}</p></Dialog>
  </section>;
}
