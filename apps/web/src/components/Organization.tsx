"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { workflowJson } from "@/lib/workflow";
import { useWorkflowText } from "@/lib/workflow-text";
import { useToast } from "./Toast";
import "./Workflow.css";

type Organization = { folder: string; tags: string[] };
export function OrganizationEditor({ entity, id }: { entity: "document" | "record"; id: number }) {
  const w = useWorkflowText();
  const toast = useToast();
  const query = useQuery({ queryKey: ["organization", entity, id], queryFn: () => workflowJson<Organization>(`/api/organization/${entity}/${id}`) });
  if (!query.data) return null;
  return <OrganizationForm key={`${entity}-${id}-${JSON.stringify(query.data)}`} entity={entity} id={id} initial={query.data} onSaved={() => toast(w.saved)} />;
}
function OrganizationForm({ entity, id, initial, onSaved }: { entity: string; id: number; initial: Organization; onSaved: () => void }) {
  const w = useWorkflowText();
  const [folder, setFolder] = useState(initial.folder);
  const [tags, setTags] = useState(initial.tags.join(", "));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const cache = useQueryClient();
  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await workflowJson(`/api/organization/${entity}/${id}`, "PUT", { folder, tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean) });
      onSaved(); await cache.invalidateQueries({ queryKey: ["organization"] });
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Erro"); }
    finally { setBusy(false); }
  };
  return <form className="panel" onSubmit={save}><div className="panel-head"><h2>{w.organize}</h2></div>
    <div className="panel-body workflow-form">
      <label className="field"><span className="field-label">{w.folder}</span><input value={folder} onChange={(event) => setFolder(event.target.value)} maxLength={100} /></label>
      <label className="field"><span className="field-label">{w.tags}</span><input value={tags} onChange={(event) => setTags(event.target.value)} /></label>
      {error && <p role="alert">{error}</p>}
      <button className="button" disabled={busy}>{w.save}</button>
    </div>
  </form>;
}

type Search = { id: number; name: string; path: string };
export function SavedSearches() {
  const w = useWorkflowText();
  const toast = useToast();
  const cache = useQueryClient();
  const pathname = usePathname();
  const params = useSearchParams();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ["saved-searches"], queryFn: () => workflowJson<Search[]>("/api/saved-searches") });
  const act = async (id?: number) => {
    setBusy(true);
    try {
      if (id) await workflowJson(`/api/saved-searches/${id}`, "DELETE");
      else { await workflowJson("/api/saved-searches", "POST", { name, path: pathname + (params.size ? `?${params}` : "") }); setName(""); }
      await cache.invalidateQueries({ queryKey: ["saved-searches"] });
    } catch (error) { toast(error instanceof Error ? error.message : "Erro", "error"); }
    finally { setBusy(false); }
  };
  return <details className="panel"><summary className="panel-head">{w.searches}</summary><div className="panel-body workflow-stack">
    <form className="workflow-row" onSubmit={(event) => { event.preventDefault(); void act(); }}>
      <label className="field"><span className="field-label">{w.searchName}</span><input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required /></label>
      <button className="button button-secondary" disabled={busy || !name.trim()}>{w.saveSearch}</button>
    </form>
    {query.error && <p role="alert">{query.error.message}</p>}
    {query.data?.map((item) => <div className="workflow-row" key={item.id}><Link className="workflow-link" href={item.path}>{item.name}</Link><button className="button button-ghost" disabled={busy} onClick={() => void act(item.id)}>{w.remove}</button></div>)}
  </div></details>;
}
