"use client";
import { SavedSearches } from "@/components/Organization";

import { Library, ScanText, SearchX } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DateRange, FilterBar, SearchInput } from "@/components/ListFilters";
import { EmptyState, ListBar, LoadMore, SkeletonRows } from "@/components/ListState";
import { ModuleIcon, moduleName, useModules } from "@/components/Modules";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { Confidence, StatusLabel } from "@/components/Status";
import { api } from "@/lib/api/endpoints";
import { useLocale } from "@/lib/i18n";
import { usePagedList, useUrlFilters } from "@/lib/lists";
import { useSession } from "@/lib/session";

const RECORD_KEYS = ["q", "module", "status", "from", "to"] as const;

export default function RecordsPage() {
  const { t, format } = useLocale();
  const { can } = useSession();
  const router = useRouter();
  const modules = useModules();
  const controls = useUrlFilters(RECORD_KEYS);
  const { values, update } = controls;
  const list = usePagedList("records", api.records, values);
  const newReading = can("documents.upload") ? (
    <Link href={values.module ? `/leitura?modulo=${values.module}` : "/leitura"} className="button">
      <ScanText size={16} strokeWidth={1.75} />
      {t.nav.newReading}
    </Link>
  ) : undefined;

  return (
    <div className={page.page}>
      <PageHead title={t.records.title} description={t.records.description} actions={newReading} />
      <section className={`panel ${page.listPanel}`}>
        <SavedSearches />
      <FilterBar>
          <SearchInput value={values.q} onSearch={(value) => update("q", value)} placeholder={t.search.placeholder} />
          <label>
            <span className="visually-hidden">{t.records.module}</span>
            <select value={values.module} onChange={(event) => update("module", event.target.value)}>
              <option value="">{t.records.allModules}</option>
              {modules.data?.map((module) => (
                <option key={module.key} value={module.key}>
                  {moduleName(t, module)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="visually-hidden">{t.records.columns.status}</span>
            <select value={values.status} onChange={(event) => update("status", event.target.value)}>
              <option value="">{t.filters.allStatus}</option>
              <option value="pending_review">{t.status.pending_review}</option>
              <option value="reviewed">{t.status.reviewed}</option>
            </select>
          </label>
          <DateRange controls={controls} label={t.records.columns.created} fromKey="from" toKey="to" />
        </FilterBar>
        <ListBar total={list.total} one={t.records.one} many={t.records.many} filtered={controls.active} onClear={controls.clear} />
        {list.total === null && !list.error ? (
          <SkeletonRows />
        ) : list.error ? null : list.items.length === 0 ? (
          controls.active ? (
            <EmptyState icon={SearchX} title={t.records.emptyFilteredTitle} text={t.records.emptyFilteredText} />
          ) : (
            <EmptyState icon={Library} title={t.records.emptyTitle} text={t.records.emptyText} action={newReading} />
          )
        ) : (
          <table className={`${page.table} ${page.clickable}`}>
            <thead>
              <tr>
                <th>{t.records.columns.title}</th>
                <th className={page.w150}>{t.records.columns.module}</th>
                <th className={`${page.w100} ${page.optional}`}>{t.records.columns.pages}</th>
                <th className={`${page.w100} ${page.optional}`}>{t.records.columns.confidence}</th>
                <th className={page.w190}>{t.records.columns.status}</th>
                <th className={`${page.w150} ${page.optional}`}>{t.records.columns.created}</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((record) => (
                <tr key={record.id} onClick={() => router.push(`/registros/${record.id}`)}>
                  <td className={page.primary}>
                    <Link href={`/registros/${record.id}`} className={page.name} onClick={(event) => event.stopPropagation()}>
                      {record.thumbnail_url ? (
                        <img className={page.thumb} src={record.thumbnail_url} alt="" loading="lazy" />
                      ) : (
                        <span className={page.thumb} />
                      )}
                      <span>{record.title || t.records.untitled}</span>
                    </Link>
                  </td>
                  <td className={page.meta}>
                    <span className="tag">
                      <ModuleIcon module={record.module} size={14} />
                      {moduleName(t, record.module)}
                    </span>
                  </td>
                  <td className={`${page.meta} ${page.optional}`}>{record.page_count || "—"}</td>
                  <td className={`${page.meta} ${page.optional}`}>
                    <Confidence value={record.confidence} />
                  </td>
                  <td className={page.meta}>
                    <StatusLabel status={record.status} />
                  </td>
                  <td className={`${page.meta} ${page.optional}`}>{format.dateTime(record.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <LoadMore onVisible={list.loadMore} enabled={list.hasMore} loading={list.loadingMore} error={list.error} />
      </section>
    </div>
  );
}
