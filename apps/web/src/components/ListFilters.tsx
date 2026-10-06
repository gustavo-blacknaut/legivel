"use client";

import { ArrowDownWideNarrow, ArrowUpNarrowWide, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useEffectEvent, useState, type ReactNode } from "react";
import { useT } from "@/lib/i18n";
import styles from "./ListFilters.module.css";

export const LIST_KEYS = ["q", "doc_type", "status", "from", "to", "sort", "order"] as const;
export type ListKey = (typeof LIST_KEYS)[number];
const SEARCH_DEBOUNCE_MS = 300;
const DOCUMENT_TYPES = { rg: "RG", cnh: "CNH", cpf: "CPF" };

type Controls<K extends string> = { values: Record<K, string>; update: (key: K, value: string) => void };

export function DateRange<K extends string>({ controls, label, fromKey, toKey }: { controls: Controls<K>; label: string; fromKey: K; toKey: K }) {
  const t = useT();
  return (
    <div className={styles.range} role="group" aria-label={label}>
      <input
        type="date"
        value={controls.values[fromKey]}
        max={controls.values[toKey] || undefined}
        onChange={(event) => controls.update(fromKey, event.target.value)}
        aria-label={t.filters.start(label)}
      />
      <span>{t.filters.until}</span>
      <input
        type="date"
        value={controls.values[toKey]}
        min={controls.values[fromKey] || undefined}
        onChange={(event) => controls.update(toKey, event.target.value)}
        aria-label={t.filters.end(label)}
      />
    </div>
  );
}

type SearchInputProps = { value: string; onSearch: (value: string) => void; placeholder: string; label?: string };

export function SearchInput({ value, onSearch, placeholder, label }: SearchInputProps) {
  const t = useT();
  const [query, setQuery] = useState(value);
  const [synced, setSynced] = useState(value);
  if (synced !== value) {
    setSynced(value);
    setQuery(value);
  }

  const submit = useEffectEvent((next: string) => onSearch(next));
  useEffect(() => {
    if (query.trim() === value) return;
    const timer = window.setTimeout(() => submit(query.trim()), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query, value]);

  return (
    <label className={styles.searchField}>
      <Search size={16} strokeWidth={1.75} />
      <span className="visually-hidden">{label ?? t.filters.search}</span>
      <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={placeholder} maxLength={120} />
    </label>
  );
}

export function FilterBar({ children, compact }: { children: ReactNode; compact?: boolean }) {
  return (
    <div className={`${styles.filters} ${compact ? styles.compact : ""}`} role="search">
      {children}
    </div>
  );
}

type ListFiltersProps = { controls: Controls<ListKey>; dateLabel: string };

export function ListFilters({ controls, dateLabel }: ListFiltersProps) {
  const t = useT();
  const { values, update } = controls;
  const [expanded, setExpanded] = useState(false);
  const order = values.order || "desc";

  const activeCount = (["doc_type", "status", "from", "to"] as const).filter((key) => values[key]).length;
  const sorts = [
    { value: "date", label: t.filters.sortDate },
    { value: "name", label: t.filters.sortName },
    { value: "status", label: t.filters.sortStatus },
  ];

  return (
    <div className={`${styles.filters} ${styles.collapsible} ${expanded ? styles.expanded : ""}`} role="search">
      <div className={styles.search}>
        <SearchInput value={values.q} onSearch={(value) => update("q", value)} placeholder={t.filters.namePlaceholder} />
        <button className={`button button-secondary ${styles.toggle}`} type="button" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>
          <SlidersHorizontal size={16} strokeWidth={1.75} />
          {t.filters.toggle}
          {activeCount > 0 && <span className={styles.count}>{activeCount}</span>}
        </button>
      </div>
      <label>
        <span className="visually-hidden">{t.documents.columns.type}</span>
        <select value={values.doc_type} onChange={(event) => update("doc_type", event.target.value)}>
          <option value="">{t.filters.allTypes}</option>
          {Object.entries(DOCUMENT_TYPES).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="visually-hidden">{t.people.columns.status}</span>
        <select value={values.status} onChange={(event) => update("status", event.target.value)}>
          <option value="">{t.filters.allStatus}</option>
          <option value="pending_review">{t.status.pending_review}</option>
          <option value="reviewed">{t.status.reviewed}</option>
        </select>
      </label>
      <DateRange controls={controls} label={dateLabel} fromKey="from" toKey="to" />
      <div className={styles.sorter}>
        <label>
          <span className="visually-hidden">{t.filters.sortBy}</span>
          <select value={values.sort || "date"} onChange={(event) => update("sort", event.target.value)}>
            {sorts.map((option) => (
              <option key={option.value} value={option.value}>
                {t.filters.sort(option.label)}
              </option>
            ))}
          </select>
        </label>
        <button
          className={`icon-button ${styles.order}`}
          type="button"
          onClick={() => update("order", order === "desc" ? "asc" : "desc")}
          aria-label={order === "desc" ? t.filters.descending : t.filters.ascending}
          title={order === "desc" ? t.filters.descending : t.filters.ascending}
        >
          {order === "desc" ? <ArrowDownWideNarrow size={16} /> : <ArrowUpNarrowWide size={16} />}
        </button>
      </div>
    </div>
  );
}

export function documentTypeLabel(type: string): string {
  return DOCUMENT_TYPES[type as keyof typeof DOCUMENT_TYPES] ?? type.toUpperCase();
}
