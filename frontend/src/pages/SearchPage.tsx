import { Search, SearchX } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { EmptyState, ListBar, SkeletonRows } from "../components/ListState";
import { StatusLabel } from "../components/Status";
import { formatDateTime, STATUS_LABELS } from "../format";
import type { SearchHit } from "../types";
import { useSentinel } from "../useInfiniteList";

const MODULE_FILTERS = [
  { value: "", label: "Todos os módulos" },
  { value: "identity", label: "Documentos de identidade" },
  { value: "cards", label: "Cartões" },
  { value: "books", label: "Livros e textos" },
  { value: "scanner", label: "Digitalização" },
  { value: "finance", label: "Financeiro" },
];
const MODULE_TAGS: Record<string, string> = {
  identity: "Identidade",
  cards: "Cartão",
  books: "Texto",
  scanner: "Scanner",
  finance: "Financeiro",
};
const PAGE_SIZE = 30;
const DEBOUNCE_MS = 300;

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [items, setItems] = useState<SearchHit[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const filterKey = ["q", "module", "status", "from", "to"].map((key) => params.get(key) ?? "").join("|");

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

  useEffect(() => {
    if (query === (params.get("q") ?? "")) return;
    const timer = window.setTimeout(() => update("q", query.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    const request = new URLSearchParams(params);
    request.set("page", String(page));
    request.set("page_size", String(PAGE_SIZE));
    setLoading(true);
    api
      .search(request)
      .then((result) => {
        if (cancelled) return;
        setTotal(result.total);
        setItems((current) => (page === 1 ? result.items : [...current, ...result.items]));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [filterKey, page]);

  useEffect(() => setPage(1), [filterKey]);

  const hasMore = total !== null && items.length < total;
  const sentinel = useSentinel(() => !loading && setPage((current) => current + 1), hasMore);
  const active = filterKey.replace(/\|/g, "") !== "";

  return (
    <div className="page page-fill">
      <PageHead title="Busca" description="Encontre qualquer registro em todos os módulos: nomes, números, valores ou trechos de texto." />
      <section className="panel list-panel">
        <div className="filters expanded">
          <label className="search search-wide">
            <span className="search-field">
              <Search size={16} strokeWidth={1.75} />
              <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar em tudo" autoFocus />
            </span>
          </label>
          <label>
            <span className="visually-hidden">Módulo</span>
            <select value={params.get("module") ?? ""} onChange={(event) => update("module", event.target.value)}>
              {MODULE_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="visually-hidden">Status</span>
            <select value={params.get("status") ?? ""} onChange={(event) => update("status", event.target.value)}>
              <option value="">Todos os status</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
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
        <ListBar total={total} singular="resultado" pluralLabel="resultados" filtered={active} onClear={() => { setQuery(""); setParams(new URLSearchParams(), { replace: true }); }} />
        <div className="list-scroll">
          {total === null ? (
            <SkeletonRows />
          ) : items.length === 0 ? (
            <EmptyState icon={SearchX} title="Nenhum resultado" text={active ? "Tente outras palavras ou remova filtros." : "Ainda não há registros processados."} />
          ) : (
            <ul className="result-list">
              {items.map((hit) => (
                <li key={`${hit.module}-${hit.id}`}>
                  <Link to={hit.url} className="result">
                    <span className="tag">{MODULE_TAGS[hit.module] ?? hit.module}</span>
                    <span className="result-main">
                      <strong>{hit.title}</strong>
                      <span className="muted">
                        {hit.subtitle} · {formatDateTime(hit.created_at)}
                      </span>
                    </span>
                    <StatusLabel status={hit.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div ref={sentinel} className="list-sentinel" />
          {loading && items.length > 0 && <div className="list-loading">Carregando mais…</div>}
        </div>
      </section>
    </div>
  );
}
