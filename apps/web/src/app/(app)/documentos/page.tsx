"use client";
import { SavedSearches } from "@/components/Organization";

import { FilePlus2, Files, SearchX } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LIST_KEYS, ListFilters, useDocumentTypeLabel } from "@/components/ListFilters";
import { EmptyState, ListBar, LoadMore, SkeletonRows } from "@/components/ListState";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { Confidence, StatusLabel } from "@/components/Status";
import { api } from "@/lib/api/endpoints";
import { formatCpf } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import { usePagedList, useUrlFilters } from "@/lib/lists";
import { useSession } from "@/lib/session";

export default function DocumentsPage() {
  const { t, format } = useLocale();
  const typeLabel = useDocumentTypeLabel();
  const { can } = useSession();
  const router = useRouter();
  const controls = useUrlFilters(LIST_KEYS, ["sort", "order"]);
  const list = usePagedList("documents", api.documents, controls.values);
  const newDocument = can("documents.upload") ? (
    <Link href="/novo" className="button">
      <FilePlus2 size={16} strokeWidth={1.75} />
      {t.nav.newDocument}
    </Link>
  ) : undefined;

  return (
    <div className={page.page}>
      <PageHead title={t.documents.title} description={t.documents.description} actions={newDocument} />
      <section className={`panel ${page.listPanel}`}>
        <SavedSearches />
      <ListFilters controls={controls} dateLabel={t.documents.dateLabel} />
        <ListBar total={list.total} one={t.documents.one} many={t.documents.many} filtered={controls.active} onClear={controls.clear} />
        {list.total === null && !list.error ? (
          <SkeletonRows />
        ) : list.error ? null : list.items.length === 0 ? (
          controls.active ? (
            <EmptyState icon={SearchX} title={t.documents.emptyFilteredTitle} text={t.documents.emptyFilteredText} />
          ) : (
            <EmptyState icon={Files} title={t.documents.emptyTitle} text={t.documents.emptyText} action={newDocument} />
          )
        ) : (
          <table className={`${page.table} ${page.clickable}`}>
            <thead>
              <tr>
                <th>{t.documents.columns.holder}</th>
                <th className={page.w80}>{t.documents.columns.type}</th>
                <th className={page.w150}>{t.documents.columns.cpf}</th>
                <th className={`${page.w100} ${page.optional}`}>{t.documents.columns.confidence}</th>
                <th className={page.w190}>{t.documents.columns.status}</th>
                <th className={`${page.w150} ${page.optional}`}>{t.documents.columns.processed}</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((document) => (
                <tr key={document.id} onClick={() => router.push(`/documentos/${document.id}`)}>
                  <td className={page.primary}>
                    <Link href={`/documentos/${document.id}`} className={page.name} onClick={(event) => event.stopPropagation()}>
                      {document.thumbnail_url ? (
                        <img className={page.thumb} src={document.thumbnail_url} alt="" loading="lazy" />
                      ) : (
                        <span className={page.thumb} />
                      )}
                      <span>{document.full_name || t.documents.unidentified}</span>
                    </Link>
                  </td>
                  <td className={page.meta}>
                    <span className="tag">{typeLabel(document.doc_type)}</span>
                  </td>
                  <td className={`${page.meta} mono`}>{formatCpf(document.cpf) || "—"}</td>
                  <td className={`${page.meta} ${page.optional}`}>
                    <Confidence value={document.confidence} />
                  </td>
                  <td className={page.meta}>
                    <StatusLabel status={document.status} />
                  </td>
                  <td className={`${page.meta} ${page.optional}`}>{format.dateTime(document.processed_at)}</td>
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
