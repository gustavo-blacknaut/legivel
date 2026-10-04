import { ArrowDownWideNarrow, ArrowUpNarrowWide, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DOCUMENT_TYPE_LABELS, STATUS_LABELS } from "../format";

const FILTER_KEYS = ["q", "doc_type", "status", "from", "to", "sort", "order"] as const;
const SEARCH_DEBOUNCE_MS = 300;
const SORT_OPTIONS = [
  { value: "date", label: "Data" },
  { value: "name", label: "Nome" },
  { value: "status", label: "Status" },
];

export function useUrlFilters() {
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => {
    const result = new URLSearchParams();
    for (const key of FILTER_KEYS) {
      const value = params.get(key);
      if (value) result.set(key, value);
    }
    return result;
  }, [params]);

  const update = (key: (typeof FILTER_KEYS)[number], value: string) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  };

  const clear = () => setParams(new URLSearchParams(), { replace: true });
  const active = FILTER_KEYS.some((key) => key !== "sort" && key !== "order" && params.get(key));

  return { filters, get: (key: string) => params.get(key) ?? "", update, clear, active };
}

type ListFiltersProps = {
  controls: ReturnType<typeof useUrlFilters>;
  dateLabel: string;
  searchPlaceholder: string;
};

export function ListFilters({ controls, dateLabel, searchPlaceholder }: ListFiltersProps) {
  const { get, update } = controls;
  const [query, setQuery] = useState(get("q"));
  const [expanded, setExpanded] = useState(false);
  const order = get("order") || "desc";

  useEffect(() => setQuery(get("q")), [get("q")]);

  useEffect(() => {
    if (query === get("q")) return;
    const timer = window.setTimeout(() => update("q", query.trim()), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const activeCount = ["doc_type", "status", "from", "to"].filter((key) => get(key)).length;

  return (
    <div className={`filters${expanded ? " expanded" : ""}`} role="search">
      <div className="search">
        <label className="search-field">
          <Search size={16} strokeWidth={1.75} />
          <span className="visually-hidden">Buscar</span>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={searchPlaceholder} />
        </label>
        <button
          className="button button-secondary filters-toggle"
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          <SlidersHorizontal size={16} strokeWidth={1.75} />
          Filtros
          {activeCount > 0 && <span className="filter-count">{activeCount}</span>}
        </button>
      </div>
      <label>
        <span className="visually-hidden">Tipo de documento</span>
        <select value={get("doc_type")} onChange={(event) => update("doc_type", event.target.value)}>
          <option value="">Todos os tipos</option>
          {Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="visually-hidden">Status</span>
        <select value={get("status")} onChange={(event) => update("status", event.target.value)}>
          <option value="">Todos os status</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div className="range" role="group" aria-label={dateLabel}>
        <input type="date" value={get("from")} max={get("to") || undefined} onChange={(event) => update("from", event.target.value)} aria-label={`${dateLabel}: início`} />
        <span>até</span>
        <input type="date" value={get("to")} min={get("from") || undefined} onChange={(event) => update("to", event.target.value)} aria-label={`${dateLabel}: fim`} />
      </div>
      <div className="sorter">
        <label>
          <span className="visually-hidden">Ordenar por</span>
          <select value={get("sort") || "date"} onChange={(event) => update("sort", event.target.value)}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                Ordenar: {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="icon-button"
          type="button"
          onClick={() => update("order", order === "desc" ? "asc" : "desc")}
          aria-label={order === "desc" ? "Ordem decrescente" : "Ordem crescente"}
          title={order === "desc" ? "Decrescente" : "Crescente"}
        >
          {order === "desc" ? <ArrowDownWideNarrow size={16} /> : <ArrowUpNarrowWide size={16} />}
        </button>
      </div>
    </div>
  );
}
