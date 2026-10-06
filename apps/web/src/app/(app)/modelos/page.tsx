"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { PageHead } from "@/components/PageHead";
import { Dialog } from "@/components/Dialog";
import page from "@/components/Page.module.css";
import { useSession } from "@/lib/session";
import { useWords } from "@/lib/maintenance-text";
import { workflowJson } from "@/lib/workflow";
import { type DocumentTemplate, type TemplateField } from "@/lib/document-templates";

const newField = (): TemplateField => ({ name: `custom_f${crypto.randomUUID().replaceAll("-", "")}`, label: "", kind: "text", required: false, expiration: false });
export default function TemplatesPage() {
  const words = useWords();
  const { can } = useSession();
  const templates = useQuery({ queryKey: ["document-templates"], queryFn: () => workflowJson<DocumentTemplate[]>("/api/document-templates") });
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [open, setOpen] = useState(false);
  const [removing, setRemoving] = useState<DocumentTemplate | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const change = (index: number, values: Partial<TemplateField>) => setFields((current) => current.map((field, position) => position === index ? { ...field, ...values } : field));
  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await workflowJson(`/api/document-templates${editing ? `/${editing}` : ""}`, editing ? "PUT" : "POST", { name, fields });
      await templates.refetch(); setOpen(false);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Erro"); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!removing) return;
    setBusy(true); setError("");
    try { await workflowJson(`/api/document-templates/${removing.id}`, "DELETE"); await templates.refetch(); setRemoving(null); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Erro"); }
    finally { setBusy(false); }
  };
  return <div className={page.page}>
    <PageHead title={words("Modelos de documentos", "Document templates")} description={words("Campos predefinidos para formulários, contratos e outras leituras recorrentes.", "Predefined fields for forms, contracts and recurring readings.")} actions={can("settings.manage") ? <button className="button" type="button" onClick={() => { setEditing(null); setName(""); setFields([newField()]); setError(""); setOpen(true); }}>{words("Novo modelo", "New template")}</button> : undefined} />
    <p>{words("Aplique um modelo na revisão de uma digitalização ou livro/texto. Identidades já usam seus campos próprios.", "Apply a template when reviewing a scan or book/text. Identities already use their own fields.")} <Link href="/leitura" className="workflow-link">{words("Nova leitura", "New reading")}</Link></p>
    {templates.error && <p role="alert">{templates.error.message}</p>}
    {templates.isLoading && <p role="status">{words("Carregando…", "Loading…")}</p>}
    {templates.data?.length === 0 && <p>{words("Nenhum modelo cadastrado. Um administrador pode criar o primeiro.", "No templates yet. An administrator can create the first one.")}</p>}
    <div className="workflow-stack">{templates.data?.map((item) => <article className="panel panel-body workflow-stack" key={item.id}>
      <h2>{item.name}</h2><ul>{item.fields.map((field) => <li key={field.name}>{field.label}{field.required ? words(" · obrigatório", " · required") : ""}{field.expiration ? words(" · validade", " · expiry") : ""}</li>)}</ul>
      {can("settings.manage") && <div className="workflow-row"><button type="button" className="button button-secondary" onClick={() => { setEditing(item.id); setName(item.name); setFields(item.fields); setError(""); setOpen(true); }}>{words("Editar modelo", "Edit template")}</button><button type="button" className="button button-danger" onClick={() => { setRemoving(item); setError(""); }}>{words("Excluir modelo", "Delete template")}</button></div>}
    </article>)}</div>
    <Dialog open={open} title={editing ? words("Editar modelo", "Edit template") : words("Novo modelo", "New template")} wide busy={busy} onClose={() => setOpen(false)} actions={<>
      <button className="button button-secondary" type="button" disabled={busy} onClick={() => setOpen(false)}>{words("Cancelar", "Cancel")}</button><button className="button" type="submit" form="template-form" disabled={busy}>{words("Salvar modelo", "Save template")}</button>
    </>}>
      <form id="template-form" className="workflow-stack" onSubmit={save}>
        <label className="field">{words("Nome do modelo", "Template name")}<input required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} disabled={busy} /></label>
        {fields.map((field, index) => <fieldset className="template-field workflow-stack" key={field.name} disabled={busy}><legend>{words(`Campo ${index + 1}`, `Field ${index + 1}`)}</legend>
          <div className="workflow-row"><label className="field">{words("Nome do campo", "Field label")}<input required maxLength={80} value={field.label} onChange={(event) => change(index, { label: event.target.value })} /></label><label className="field">{words("Formato do campo", "Field format")}<select value={field.kind} onChange={(event) => change(index, { kind: event.target.value as TemplateField["kind"], expiration: false })}><option value="text">{words("Texto", "Text")}</option><option value="textarea">{words("Texto longo", "Long text")}</option><option value="date">{words("Data", "Date")}</option></select></label></div>
          <div className="workflow-row"><label className="workflow-row"><input type="checkbox" checked={field.required} onChange={(event) => change(index, { required: event.target.checked })} />{words("Obrigatório", "Required")}</label>{field.kind === "date" && <label className="workflow-row"><input type="checkbox" checked={field.expiration} onChange={(event) => setFields((current) => current.map((item, position) => ({ ...item, expiration: position === index ? event.target.checked : false })))} />{words("Usar nos alertas de vencimento", "Use for expiry alerts")}</label>}<button className="button button-secondary" type="button" disabled={fields.length === 1} onClick={() => setFields((current) => current.filter((_, position) => position !== index))}>{words("Remover campo", "Remove field")}</button></div>
        </fieldset>)}
        <button type="button" className="button button-secondary" disabled={busy || fields.length >= 30} onClick={() => setFields((current) => [...current, newField()])}>{words("Adicionar campo", "Add field")}</button>
        <p>{words("Mudanças no modelo valem para novas aplicações. Leituras existentes preservam os campos e os dados.", "Template changes apply to new applications. Existing readings retain their fields and data.")}</p>
        {error && <p role="alert">{error}</p>}
      </form>
    </Dialog>
    <Dialog open={!!removing} title={words("Excluir modelo?", "Delete template?")} busy={busy} onClose={() => setRemoving(null)} actions={<><button className="button button-secondary" type="button" disabled={busy} onClick={() => setRemoving(null)}>{words("Cancelar", "Cancel")}</button><button className="button button-danger" type="button" disabled={busy} onClick={remove}>{words("Excluir", "Delete")}</button></>}><p>{words("As leituras que já usam este modelo manterão seus campos e dados.", "Readings already using this template will retain their fields and data.")}</p>{error && <p role="alert">{error}</p>}</Dialog>
  </div>;
}
