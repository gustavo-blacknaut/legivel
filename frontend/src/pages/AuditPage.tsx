import { ScrollText, SearchX } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { EmptyState, ListBar, SkeletonRows } from "../components/ListState";
import { formatDateTime, getTimeZone } from "../format";
import type { AuditEntry } from "../types";
import { useInfiniteList, useSentinel } from "../useInfiniteList";

const ACTION_LABELS: Record<string, string> = {
  login: "Entrou no sistema",
  login_failed: "Tentativa de login recusada",
  logout: "Saiu do sistema",
  view: "Visualizou",
  create: "Criou",
  update: "Editou",
  review: "Revisou",
  verify: "Verificou",
  reprocess: "Reprocessou",
  delete: "Apagou",
  revoke: "Revogou",
  upload: "Recebeu envio",
};
const ENTITY_LABELS: Record<string, string> = {
  document: "Documento",
  person: "Pessoa",
  user: "Usuário",
  image: "Imagem",
  settings: "Configurações",
  session: "Sessões",
  scan_link: "Link de envio",
};
const ENTITY_ROUTES: Record<string, string> = { document: "/documentos", person: "/pessoas" };
const FILTER_KEYS = ["action", "entity", "from", "to"];

function EntityReference({ entry }: { entry: AuditEntry }) {
  const label = ENTITY_LABELS[entry.entity] ?? entry.entity;
  const route = ENTITY_ROUTES[entry.entity];
  if (entry.entity_id === null) return <>{label}</>;
  if (route && entry.action !== "delete") {
    return (
      <Link to={`${route}/${entry.entity_id}`} className="audit-link">
        {label} #{entry.entity_id}
      </Link>
    );
  }
  return (
    <>
      {label} <span className="mono">#{entry.entity_id}</span>
    </>
  );
}

export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const filters = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = params.get(key);
    if (value) filters.set(key, value);
  }
  const list = useInfiniteList(api.audit, filters);
  const sentinel = useSentinel(list.loadMore, list.hasMore);
  const active = filters.toString() !== "";

  const update = (key: string, value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );

  return (
    <div className="page page-fill">
      <PageHead title="Auditoria" description={`Todas as ações registradas, com data e hora em ${getTimeZone().replace("_", " ")}.`} />
      <section className="panel list-panel">
        <div className="filters filters-compact expanded">
          <label>
            <span className="visually-hidden">Ação</span>
            <select value={params.get("action") ?? ""} onChange={(event) => update("action", event.target.value)}>
              <option value="">Todas as ações</option>
              {Object.entries(ACTION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="visually-hidden">Registro</span>
            <select value={params.get("entity") ?? ""} onChange={(event) => update("entity", event.target.value)}>
              <option value="">Todos os registros</option>
              {Object.entries(ENTITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <div className="range" role="group" aria-label="Período">
            <input type="date" value={params.get("from") ?? ""} onChange={(event) => update("from", event.target.value)} aria-label="Período: início" />
            <span>até</span>
            <input type="date" value={params.get("to") ?? ""} onChange={(event) => update("to", event.target.value)} aria-label="Período: fim" />
          </div>
        </div>
        <ListBar total={list.total} singular="registro" pluralLabel="registros" filtered={active} onClear={() => setParams(new URLSearchParams(), { replace: true })} />
        <div className="list-scroll">
          {list.total === null && !list.error ? (
            <SkeletonRows />
          ) : list.items.length === 0 ? (
            <EmptyState icon={active ? SearchX : ScrollText} title="Nenhum registro" text={active ? "Nenhuma ação no período ou filtro escolhido." : "As ações aparecem aqui conforme o sistema é usado."} />
          ) : (
            <table className="table table-static audit-table">
              <thead>
                <tr>
                  <th className="w-190">Data e hora</th>
                  <th className="w-130">Usuário</th>
                  <th className="w-190">Ação</th>
                  <th>Registro</th>
                  <th className="col-optional">Detalhes</th>
                  <th className="w-130 col-optional">IP</th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((entry) => (
                  <tr key={entry.id} className={entry.action === "login_failed" || entry.action === "delete" ? "audit-alert" : undefined}>
                    <td className="audit-when mono">{formatDateTime(entry.occurred_at, true)}</td>
                    <td className="audit-user">{entry.username ?? (entry.action === "upload" ? "Link público" : "—")}</td>
                    <td className="audit-action">{ACTION_LABELS[entry.action] ?? entry.action}</td>
                    <td className="audit-entity"><EntityReference entry={entry} /></td>
                    <td className="audit-details col-optional">{entry.details ?? ""}</td>
                    <td className="audit-ip mono col-optional">{entry.ip_address ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div ref={sentinel} className="list-sentinel" />
          {list.loading && list.items.length > 0 && <div className="list-loading">Carregando mais…</div>}
        </div>
      </section>
    </div>
  );
}
