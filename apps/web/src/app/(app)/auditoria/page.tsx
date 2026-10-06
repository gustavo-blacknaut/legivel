"use client";

import { ScrollText, SearchX } from "lucide-react";
import Link from "next/link";
import { Forbidden } from "@/components/Forbidden";
import { DateRange, FilterBar } from "@/components/ListFilters";
import { EmptyState, ListBar, LoadMore, SkeletonRows } from "@/components/ListState";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { api, type AuditEntry } from "@/lib/api/endpoints";
import { useLocale } from "@/lib/i18n";
import { usePagedList, useUrlFilters } from "@/lib/lists";
import { useSession } from "@/lib/session";
import styles from "./audit.module.css";

const KEYS = ["action", "entity", "from", "to"] as const;
const ROUTES: Record<string, string> = { document: "/documentos", person: "/pessoas" };
const ALERT_ACTIONS = new Set(["login_failed", "delete", "lock", "2fa_failed", "retention"]);

function EntityReference({ entry }: { entry: AuditEntry }) {
  const { t } = useLocale();
  const label = t.audit.entities[entry.entity] ?? entry.entity;
  const route = ROUTES[entry.entity];
  if (entry.entity_id === null || entry.entity_id === undefined) return <>{label}</>;
  if (route && entry.action !== "delete") {
    return (
      <Link href={`${route}/${entry.entity_id}`} className={styles.link}>
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

export default function AuditPage() {
  const { t, format, timeZone } = useLocale();
  const { can } = useSession();
  const controls = useUrlFilters(KEYS);
  const list = usePagedList("audit", api.audit, controls.values);
  if (!can("audit.view")) return <Forbidden />;

  return (
    <div className={page.page}>
      <PageHead title={t.audit.title} description={t.audit.description(timeZone.replace(/_/g, " "))} />
      <section className={`panel ${page.listPanel}`}>
        <FilterBar compact>
          <label>
            <span className="visually-hidden">{t.audit.action}</span>
            <select value={controls.values.action} onChange={(event) => controls.update("action", event.target.value)}>
              <option value="">{t.audit.allActions}</option>
              {Object.entries(t.audit.actions).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="visually-hidden">{t.audit.entity}</span>
            <select value={controls.values.entity} onChange={(event) => controls.update("entity", event.target.value)}>
              <option value="">{t.audit.allEntities}</option>
              {Object.entries(t.audit.entities).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <DateRange controls={controls} label={t.audit.period} fromKey="from" toKey="to" />
        </FilterBar>
        <ListBar total={list.total} one={t.audit.one} many={t.audit.many} filtered={controls.active} onClear={controls.clear} />
        {list.total === null && !list.error ? (
          <SkeletonRows />
        ) : list.error ? null : list.items.length === 0 ? (
          <EmptyState icon={controls.active ? SearchX : ScrollText} title={t.audit.emptyTitle} text={controls.active ? t.audit.emptyFiltered : t.audit.emptyText} />
        ) : (
          <table className={`${page.table} ${styles.table}`}>
            <thead>
              <tr>
                <th className={page.w190}>{t.audit.columns.when}</th>
                <th className={page.w150}>{t.audit.columns.user}</th>
                <th className={page.w190}>{t.audit.columns.action}</th>
                <th>{t.audit.columns.entity}</th>
                <th className={page.optional}>{t.audit.columns.details}</th>
                <th className={`${page.w130} ${page.optional}`}>{t.audit.columns.ip}</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((entry) => (
                <tr key={entry.id} className={ALERT_ACTIONS.has(entry.action) ? styles.alert : undefined}>
                  <td className={`${styles.when} mono`}>{format.dateTime(entry.occurred_at, true)}</td>
                  <td className={styles.user}>{entry.user ?? (entry.action === "retention" ? t.audit.system : t.audit.publicLink)}</td>
                  <td className={styles.action}>{t.audit.actions[entry.action] ?? entry.action}</td>
                  <td className={styles.entity}>
                    <EntityReference entry={entry} />
                  </td>
                  <td className={`${styles.details} ${page.optional} ${page.wrap}`}>{entry.details ?? ""}</td>
                  <td className={`${styles.ip} mono ${page.optional}`}>{entry.ip_address ?? "—"}</td>
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
