"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { PageHead } from "@/components/PageHead";
import { SavedSearches } from "@/components/Organization";
import page from "@/components/Page.module.css";
import { workflowJson } from "@/lib/workflow";
import { useWorkflowText } from "@/lib/workflow-text";
import "@/components/Workflow.css";
type Entry = { id: number; entity: string; title: string; folder: string; tags: string[] };
export default function OrganizationPage() {
  const w = useWorkflowText();
  const params = useSearchParams();
  const router = useRouter();
  const folder = params.get("folder") ?? "";
  const tag = params.get("tag") ?? "";
  const query = useQuery({ queryKey: ["organization"], queryFn: () => workflowJson<Entry[]>("/api/organization") });
  const update = (key: string, value: string) => { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); router.replace(`/organizar?${next}`); };
  const entries = query.data ?? [];
  return <div className={page.page}>
    <PageHead title={w.organize} /><SavedSearches />
    <div className="workflow-row">
      <label className="field"><span className="field-label">{w.folder}</span><select aria-label={w.folder} value={folder} onChange={(event) => update("folder", event.target.value)}><option value="">{w.allFolders}</option>{Array.from(new Set(entries.map((item) => item.folder).filter(Boolean))).sort().map((item) => <option key={item}>{item}</option>)}</select></label>
      <label className="field"><span className="field-label">{w.tags}</span><select aria-label={w.tags} value={tag} onChange={(event) => update("tag", event.target.value)}><option value="">{w.allTags}</option>{Array.from(new Set(entries.flatMap((item) => item.tags))).sort().map((item) => <option key={item}>{item}</option>)}</select></label>
    </div>
    {query.error && <p role="alert">{query.error.message}</p>}
    <section className="panel">{entries.filter((item) => (!folder || item.folder === folder) && (!tag || item.tags.includes(tag))).map((item) => <article className="workflow-item" key={`${item.entity}-${item.id}`}>
      <Link className="workflow-link" href={`/${item.entity === "document" ? "documentos" : "registros"}/${item.id}`}>{item.title}</Link><span>{item.folder} · {item.tags.join(", ")}</span>
    </article>)}{!query.isPending && !entries.length && <p className="panel-body">{w.empty}</p>}</section>
  </div>;
}
