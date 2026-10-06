"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "@/lib/session";
import { useWords } from "@/lib/maintenance-text";
import { workflowJson } from "@/lib/workflow";
import { type DocumentTemplate } from "@/lib/document-templates";
import { Dialog } from "./Dialog";

export function TemplatePicker({ id, module, template, dirty }: { id: number; module: string; template: { name?: string } | null | undefined; dirty: boolean }) {
  const words = useWords();
  const { can } = useSession();
  const client = useQueryClient();
  const enabled = ["scanner", "books"].includes(module) && can("documents.review");
  const templates = useQuery({ queryKey: ["document-templates"], queryFn: () => workflowJson<DocumentTemplate[]>("/api/document-templates"), enabled });
  const [selected, setSelected] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!enabled) return null;
  if (template) return <p className="alert alert-info">{words("Modelo aplicado", "Applied template")}: {template.name}</p>;
  const apply = async () => {
    setBusy(true); setError("");
    try {
      await workflowJson(`/api/records/${id}/template`, "POST", { template_id: selected });
      await client.invalidateQueries({ queryKey: ["record", id] });
      setConfirm(false);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Erro"); }
    finally { setBusy(false); }
  };
  return <section className="panel panel-body workflow-stack">
    <h2>{words("Modelo de documento", "Document template")}</h2>
    <p>{words("Acrescente os campos de um formulário recorrente. Use o texto extraído como referência para preenchê-los.", "Add fields for a recurring form. Use the extracted text as a reference when filling them in.")}</p>
    {templates.error && <p role="alert">{templates.error.message}</p>}
    <label className="field">{words("Escolher modelo", "Choose template")}<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">{words("Selecione…", "Select…")}</option>{templates.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    {dirty && <p>{words("Salve as alterações do formulário antes de aplicar um modelo.", "Save your form changes before applying a template.")}</p>}
    <div className="workflow-row"><button className="button button-secondary" type="button" disabled={!selected || dirty || busy} onClick={() => setConfirm(true)}>{words("Aplicar modelo", "Apply template")}</button><Link className="workflow-link" href="/modelos">{words("Ver modelos", "View templates")}</Link></div>
    <Dialog open={confirm} title={words("Aplicar este modelo?", "Apply this template?")} busy={busy} onClose={() => setConfirm(false)} actions={<>
      <button className="button button-secondary" type="button" disabled={busy} onClick={() => setConfirm(false)}>{words("Cancelar", "Cancel")}</button><button className="button" type="button" disabled={busy} onClick={apply}>{words("Aplicar", "Apply")}</button>
    </>}><p>{words("Os campos serão acrescentados a esta leitura e permanecerão disponíveis mesmo se o modelo for alterado ou excluído.", "Fields will be added to this reading and remain available if the template is edited or deleted.")}</p>{error && <p role="alert">{error}</p>}</Dialog>
  </section>;
}
