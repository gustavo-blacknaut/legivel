"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Download, FileText, Save, ShieldCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { ReviewHistory } from "@/components/ReviewHistory";
import { ImageComparison } from "@/components/ImageComparison";
import { BatchReviewBar } from "@/components/BatchReviewBar";
import { TemplatePicker } from "@/components/TemplatePicker";
import { useBatchReview } from "@/lib/batch-review";
import { OrganizationEditor } from "@/components/Organization";
import { RedactionExport } from "@/components/RedactionExport";
import { DeleteDialog } from "@/components/DeleteDialog";
import { Lightbox } from "@/components/Lightbox";
import { EmptyState } from "@/components/ListState";
import { ModuleIcon, moduleName } from "@/components/Modules";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import styles from "@/components/Review.module.css";
import { Confidence, StatusLabel } from "@/components/Status";
import { useToast } from "@/components/Toast";
import { api, type RecordDetail, type RecordField } from "@/lib/api/endpoints";
import { confidenceLevel, formatPercent } from "@/lib/format";
import { useLocale, useT } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import view from "./record.module.css";

const LOCKED_KINDS = new Set(["readonly", "masked"]);
const EXPORT_LABELS: Record<string, string> = { pdf: "PDF", txt: "TXT", md: "Markdown" };

function valuesOf(record: RecordDetail): Record<string, string> {
  return Object.fromEntries(record.fields.map((field) => [field.name, field.value]));
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function RecordPage() {
  const { t, format } = useLocale();
  const { can } = useSession();
  const recordId = Number(useParams<{ id: string }>().id);
  const batch = useBatchReview("record", recordId);
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["record", recordId], queryFn: () => api.record(recordId), enabled: Number.isFinite(recordId) });
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [viewer, setViewer] = useState<string | null>(null);
  const record = detail.data;
  const editable = can("documents.review");

  const [synced, setSynced] = useState<RecordDetail | undefined>(undefined);
  if (record !== synced) {
    setSynced(record);
    if (record) setValues(valuesOf(record));
  }

  const changed = useMemo(
    () => record?.fields.filter((field) => !LOCKED_KINDS.has(field.kind) && (values[field.name] ?? "") !== field.value) ?? [],
    [record, values],
  );

  if (detail.error) {
    return (
      <div className={page.page}>
        <EmptyState
          icon={CircleAlert}
          title={detail.error.message}
          text={t.record.notFound}
          action={
            <Link href="/registros" className="button button-secondary">
              {t.nav.readings}
            </Link>
          }
        />
      </div>
    );
  }
  if (!record) return <div className="spinner spinner-page" role="status" />;

  const title = record.title || t.records.untitled;

  const save = async (event?: FormEvent, advance = false) => {
    event?.preventDefault();
    setSaving(true);
    try {
      const next = await api.saveRecord(record.id, Object.fromEntries(changed.map((field) => [field.name, values[field.name] ?? ""])));
      queryClient.setQueryData(["record", recordId], next);
      setValues(valuesOf(next));
      void queryClient.invalidateQueries({ queryKey: ["records"] });
      toast(t.record.saved);
      void queryClient.invalidateQueries({ queryKey: ["expirations"] });
      if (advance) batch.navigate(1, true);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    } finally {
      setSaving(false);
    }
  };

  const exportAs = async (type: string) => {
    setExporting(type);
    try {
      download(await api.exportRecord(record.id, type), `legivel-${record.module}-${record.id}.${type}`);
    } catch {
      toast(t.record.exportFailed, "error");
    } finally {
      setExporting(null);
    }
  };

  const remove = async () => {
    await api.deleteRecord(record.id);
    toast(t.record.deleted);
    void queryClient.invalidateQueries({ queryKey: ["records"] });
    router.push("/registros");
  };

  const language = record.language ? t.record.language(t.settings.languageNames[record.language] ?? record.language) : "";

  return (
    <div className={page.page}>
      <PageHead
        back={{ href: `/registros?module=${record.module}`, label: t.record.back }}
        title={title}
        description={
          <span className={view.subtitle}>
            <ModuleIcon module={record.module} size={14} />
            {moduleName(t, { key: record.module, name: record.module_name })}
            {record.kind_label && ` · ${record.kind_label}`}
            {language}
            {` · ${t.record.readAt(format.dateTime(record.created_at))}`}
          </span>
        }
        actions={<StatusLabel status={record.status} />}
      />

      {!editable && <div className="alert alert-warning">{t.record.readOnly}</div>}
      <BatchReviewBar batch={batch} dirty={changed.length > 0} busy={saving} onSave={() => void save(undefined, true)} />
      <ImageComparison pages={record.pages.map((item) => ({ label: t.reading.pageLabel(item.number), original: item.original_url, processed: item.full_url }))} />
      {record.issues.length > 0 && (
        <div className="alert alert-warning">
          <CircleAlert size={16} />
          <span>{record.issues.map((issue) => issue.message).join(" ")}</span>
        </div>
      )}

      <div className={record.pages.length > 0 ? styles.review : view.single}>
        {record.pages.length > 0 && (
          <aside className={styles.images} aria-label={t.record.pages}>
            {record.pages.map((item) =>
              item.thumbnail_url ? (
                <button key={item.id} type="button" className={styles.imageButton} onClick={() => setViewer(item.full_url ?? item.thumbnail_url)}>
                  <img src={item.thumbnail_url} alt={t.reading.pageLabel(item.number)} />
                  <span className={styles.caption}>
                    <span>{t.reading.pageLabel(item.number)}</span>
                    <span>{t.review.enlarge}</span>
                  </span>
                </button>
              ) : null,
            )}
          </aside>
        )}

        <div className="stack">
          <TemplatePicker id={recordId} module={record.module} template={record.template} dirty={changed.length > 0} />
          <form className="panel" onSubmit={save}>
            <div className="panel-head">
              <h2>{t.record.fields}</h2>
              <span className="muted">
                {t.review.averageConfidence} <Confidence value={record.confidence} />
              </span>
            </div>
            {record.card && (
              <p className={`panel-body muted flush ${view.note}`}>
                <ShieldCheck size={14} strokeWidth={1.75} />
                {record.card.number_stored ? t.record.numberStored : t.record.numberNotStored}
              </p>
            )}
            {record.fields.length === 0 ? (
              <p className="panel-body muted flush">{t.record.noFields}</p>
            ) : (
              <fieldset disabled={!editable} className={styles.fieldset}>
                <div className={`form-grid ${styles.section}`}>
                  {record.fields.map((field) => (
                    <RecordInput
                      key={field.name}
                      field={field}
                      value={values[field.name] ?? ""}
                      onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))}
                    />
                  ))}
                </div>
              </fieldset>
            )}
            {editable && (
              <div className={`panel-foot ${styles.footer}`}>
                {changed.length > 0 && <span className={styles.unsaved}>{t.review.unsaved}</span>}
                <button className="button button-lg" type="submit" disabled={saving}>
                  <Save size={16} strokeWidth={1.75} />
                  {saving ? t.common.saving : t.record.confirm}
                </button>
              </div>
            )}
          </form>

          {record.pages.some((item) => item.text) && (
            <section className="panel">
              <div className="panel-head">
                <h2>{t.record.pages}</h2>
              </div>
              <div className="panel-body stack">
                {record.pages.map((item) => (
                  <details key={item.id} open={record.pages.length === 1}>
                    <summary className={`muted ${styles.rawSummary} ${view.note}`}>
                      <FileText size={14} strokeWidth={1.75} />
                      {t.record.pageText(item.number)}
                      {t.record.columns(item.columns ?? 1)}
                    </summary>
                    <pre className={view.text}>{item.text || t.record.emptyText}</pre>
                  </details>
                ))}
              </div>
            </section>
          )}

          {(record.exports.length > 0 || can("documents.delete")) && (
            <section className="panel">
              <div className="panel-body actions-row">
                {record.exports.map((type) => (
                  <button key={type} className="button button-secondary" type="button" onClick={() => exportAs(type)} disabled={exporting !== null}>
                    <Download size={16} strokeWidth={1.75} className={exporting === type ? "spin" : undefined} />
                    {`${t.record.exports} ${EXPORT_LABELS[type] ?? type.toUpperCase()}`}
                  </button>
                ))}
                {can("documents.delete") && (
                  <button className="button button-danger-ghost" type="button" onClick={() => setDeleting(true)}>
                    <Trash2 size={16} strokeWidth={1.75} />
                    {t.record.delete}
                  </button>
                )}
              </div>
            </section>
          )}
        </div>
      </div>

      <ReviewHistory entity="record" id={record.id} />
      <OrganizationEditor entity="record" id={record.id} />
      <RedactionExport key={record.id} entity="record" id={record.id} pages={record.pages} />
      <DeleteDialog
        open={deleting}
        title={t.record.deleteTitle}
        description={t.record.deleteDescription(title)}
        documents={1}
        images={record.pages.length}
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      />
      <Lightbox src={viewer} onClose={() => setViewer(null)} />
    </div>
  );
}

type RecordInputProps = { field: RecordField; value: string; onChange: (name: string, value: string) => void };

function RecordInput({ field, value, onChange }: RecordInputProps) {
  const t = useT();
  const locked = LOCKED_KINDS.has(field.kind);
  const untouched = value === field.value;
  const level = value && untouched ? confidenceLevel(field.confidence) : "unknown";
  const levelClass = level === "high" ? styles.high : level === "medium" ? styles.medium : level === "low" ? styles.low : "";
  const inputId = `record-${field.name}`;
  const long = value.length > 48;
  return (
    <div className={["field", long ? "span-2" : "", level === "low" ? styles.lowField : "", field.issues.length ? "field-invalid" : ""].filter(Boolean).join(" ")}>
      <label className="field-label" htmlFor={inputId}>
        {field.label}
        {value && untouched && field.confidence !== null && field.confidence !== undefined && (
          <span className={`${styles.confidence} ${levelClass}`} title={t.review.ocrConfidence}>
            {formatPercent(field.confidence)}
          </span>
        )}
        {value && !untouched && <span className={styles.confidence}>{t.review.edited}</span>}
      </label>
      {field.kind === "textarea" ? <textarea id={inputId} value={value} maxLength={500} rows={4} onChange={(event) => onChange(field.name, event.target.value)} aria-invalid={field.issues.length > 0 || undefined} /> : <input
        id={inputId}
        value={value}
        type={field.kind === "date" && field.name.startsWith("custom_") ? "date" : "text"}
        maxLength={500}
        readOnly={locked}
        onChange={(event) => onChange(field.name, event.target.value)}
        inputMode={field.kind === "date" ? "numeric" : undefined}
        placeholder={field.kind === "date" ? "dd/mm/aaaa" : undefined}
        className={locked ? "mono" : undefined}
        aria-invalid={field.issues.length > 0 || undefined}
      />}
      {field.issues.map((issue) => (
        <span key={issue} className="field-error">
          {issue}
        </span>
      ))}
    </div>
  );
}
