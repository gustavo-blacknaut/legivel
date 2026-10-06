"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { IdCard, Search, SearchX } from "lucide-react";
import Link from "next/link";
import { FilterBar, SearchInput } from "@/components/ListFilters";
import { EmptyState, SkeletonRows } from "@/components/ListState";
import { ModuleIcon, moduleName, useModules } from "@/components/Modules";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { StatusLabel } from "@/components/Status";
import { api } from "@/lib/api/endpoints";
import { useLocale } from "@/lib/i18n";
import { useUrlFilters } from "@/lib/lists";
import styles from "./search.module.css";

const SEARCH_KEYS = ["q", "module"] as const;
const MIN_LENGTH = 2;

export default function SearchPage() {
  const { t, format } = useLocale();
  const modules = useModules();
  const controls = useUrlFilters(SEARCH_KEYS);
  const { values, update } = controls;
  const ready = values.q.length >= MIN_LENGTH;
  const results = useQuery({
    queryKey: ["search", values],
    queryFn: () => api.search({ q: values.q, module: values.module || undefined }),
    enabled: ready,
    placeholderData: keepPreviousData,
  });

  return (
    <div className={page.page}>
      <PageHead title={t.search.title} description={t.search.description} />
      <section className={`panel ${page.listPanel}`}>
        <FilterBar>
          <SearchInput value={values.q} onSearch={(value) => update("q", value)} placeholder={t.search.placeholder} label={t.search.title} />
          <label>
            <span className="visually-hidden">{t.records.module}</span>
            <select value={values.module} onChange={(event) => update("module", event.target.value)}>
              <option value="">{t.search.everywhere}</option>
              <option value="identity">{t.search.identity}</option>
              {modules.data?.map((module) => (
                <option key={module.key} value={module.key}>
                  {moduleName(t, module)}
                </option>
              ))}
            </select>
          </label>
        </FilterBar>
        {!ready ? (
          <EmptyState icon={Search} title={t.search.title} text={t.search.hint} />
        ) : !results.data ? (
          <SkeletonRows />
        ) : results.data.items.length === 0 ? (
          <EmptyState icon={SearchX} title={t.search.emptyTitle} text={t.search.emptyText} />
        ) : (
          <>
            <p className={styles.total}>
              {results.data.total.toLocaleString()} {results.data.total === 1 ? t.search.one : t.search.many}
            </p>
            <ul className={styles.hits}>
              {results.data.items.map((hit) => (
                <li key={`${hit.module}-${hit.id}`}>
                  <Link href={hit.url} className={styles.hit}>
                    <span className={styles.icon}>
                      {hit.module === "identity" ? <IdCard size={18} strokeWidth={1.75} /> : <ModuleIcon module={hit.module} />}
                    </span>
                    <span className={styles.text}>
                      <strong>{hit.title}</strong>
                      <span>
                        {hit.module === "identity" ? hit.subtitle : moduleName(t, hit.module)} · {format.dateTime(hit.created_at)}
                      </span>
                    </span>
                    <StatusLabel status={hit.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}
