"use client";
import { SavedSearches } from "@/components/Organization";

import { FilePlus2, SearchX, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { DeleteDialog } from "@/components/DeleteDialog";
import { LIST_KEYS, ListFilters, useDocumentTypeLabel } from "@/components/ListFilters";
import { EmptyState, ListBar, LoadMore, SkeletonRows } from "@/components/ListState";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { StatusLabel } from "@/components/Status";
import { useToast } from "@/components/Toast";
import { api, type Person } from "@/lib/api/endpoints";
import { formatCpf, initials } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import { usePagedList, useUrlFilters } from "@/lib/lists";
import { useSession } from "@/lib/session";

export default function PeoplePage() {
  const { t, format } = useLocale();
  const typeLabel = useDocumentTypeLabel();
  const { can } = useSession();
  const router = useRouter();
  const toast = useToast();
  const controls = useUrlFilters(LIST_KEYS, ["sort", "order"]);
  const list = usePagedList("people", api.people, controls.values);
  const [pending, setPending] = useState<Person | null>(null);
  const canDelete = can("people.delete");
  const canUpload = can("documents.upload");
  const newDocument = canUpload ? (
    <Link href="/novo" className="button">
      <FilePlus2 size={16} strokeWidth={1.75} />
      {t.nav.newDocument}
    </Link>
  ) : undefined;

  const remove = async () => {
    if (!pending) return;
    await api.deletePerson(pending.id);
    await list.remove(pending.id);
    toast(t.people.deleted(pending.full_name ?? t.people.fallbackName));
    setPending(null);
  };

  return (
    <div className={page.page}>
      <PageHead title={t.people.title} description={t.people.description} actions={newDocument} />
      <section className={`panel ${page.listPanel}`}>
        <SavedSearches />
      <ListFilters controls={controls} dateLabel={t.people.dateLabel} />
        <ListBar total={list.total} one={t.people.one} many={t.people.many} filtered={controls.active} onClear={controls.clear} />
        {list.total === null && !list.error ? (
          <SkeletonRows />
        ) : list.error ? null : list.items.length === 0 ? (
          controls.active ? (
            <EmptyState icon={SearchX} title={t.people.emptyFilteredTitle} text={t.people.emptyFilteredText} />
          ) : (
            <EmptyState icon={Users} title={t.people.emptyTitle} text={t.people.emptyText} action={newDocument} />
          )
        ) : (
          <table className={`${page.table} ${page.clickable}`}>
            <thead>
              <tr>
                <th>{t.people.columns.name}</th>
                <th className={page.w150}>{t.people.columns.cpf}</th>
                <th className={`${page.w130} ${page.optional}`}>{t.people.columns.documents}</th>
                <th className={page.w190}>{t.people.columns.status}</th>
                <th className={`${page.w120} ${page.optional}`}>{t.people.columns.created}</th>
                {canDelete && (
                  <th className={page.actions}>
                    <span className="visually-hidden">{t.people.columns.actions}</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {list.items.map((person) => (
                <tr key={person.id} onClick={() => router.push(`/pessoas/${person.id}`)}>
                  <td className={page.primary}>
                    <Link href={`/pessoas/${person.id}`} className={page.name} onClick={(event) => event.stopPropagation()}>
                      <span className="avatar" aria-hidden="true">
                        {initials(person.full_name)}
                      </span>
                      <span>{person.full_name || t.people.unnamed}</span>
                    </Link>
                  </td>
                  <td className={`${page.meta} mono`}>{formatCpf(person.cpf) || "—"}</td>
                  <td className={`${page.meta} ${page.optional}`}>{person.doc_types.map(typeLabel).join(" · ") || "—"}</td>
                  <td className={page.meta}>
                    <StatusLabel status={person.status} />
                  </td>
                  <td className={`${page.meta} ${page.optional}`}>{format.date(person.created_at)}</td>
                  {canDelete && (
                    <td className={page.actions}>
                      <button
                        className="icon-button"
                        type="button"
                        aria-label={t.people.deleteLabel(person.full_name ?? t.people.fallbackName)}
                        onClick={(event) => {
                          event.stopPropagation();
                          setPending(person);
                        }}
                      >
                        <Trash2 size={16} strokeWidth={1.75} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <LoadMore onVisible={list.loadMore} enabled={list.hasMore} loading={list.loadingMore} error={list.error} />
      </section>
      <DeleteDialog
        open={pending !== null}
        title={t.people.deleteTitle}
        description={t.people.deleteDescription(pending?.full_name ?? t.people.fallbackName)}
        documents={pending?.documents ?? 0}
        images={pending?.images ?? 0}
        confirmationValues={[pending?.full_name ?? "", pending?.cpf ?? ""]}
        confirmationLabel={t.people.deleteConfirm}
        onConfirm={remove}
        onClose={() => setPending(null)}
      />
    </div>
  );
}
