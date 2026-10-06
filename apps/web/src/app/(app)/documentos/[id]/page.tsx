"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpDown, ChevronDown, CircleAlert, Eye, FileSearch, IdCard, RefreshCw, Save, Trash2, UserRound } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { FieldCrop, type FieldRegion } from "@/components/FieldCrop";
import { OrganizationEditor } from "@/components/Organization";
import { RedactionExport } from "@/components/RedactionExport";
import { useWorkflowText } from "@/lib/workflow-text";
import { DeleteDialog } from "@/components/DeleteDialog";
import { Lightbox } from "@/components/Lightbox";
import { EmptyState } from "@/components/ListState";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import styles from "@/components/Review.module.css";
import { Confidence, StatusLabel } from "@/components/Status";
import { useToast } from "@/components/Toast";
import { api, type DocumentDetail, type Field } from "@/lib/api/endpoints";
import { confidenceLevel, formatPercent } from "@/lib/format";
import { useLocale, useT } from "@/lib/i18n";
import { useSession } from "@/lib/session";

const WIDE_FIELDS = new Set(["full_name", "mother_name", "father_name", "mrz_raw", "civil_registry"]);

function valuesOf(document: DocumentDetail): Record<string, string> {
  return Object.fromEntries(document.fields.map((field) => [field.name, field.value]));
}

export default function DocumentPage() {
  const { t, format } = useLocale();
  const w = useWorkflowText();
  const [activeField, setActiveField] = useState<string | null>(null);
  const { can } = useSession();
  const documentId = Number(useParams<{ id: string }>().id);
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [reveal, setReveal] = useState(false);
  const detail = useQuery({
    queryKey: ["document", documentId, reveal],
    queryFn: () => api.document(documentId, reveal),
    enabled: Number.isFinite(documentId),
  });
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [viewer, setViewer] = useState<string | null>(null);
  const document = detail.data;
  const editable = can("documents.review");

  const [synced, setSynced] = useState<DocumentDetail | undefined>(undefined);
  if (document !== synced) {
    setSynced(document);
    if (document) setValues(valuesOf(document));
  }

  const dirty = useMemo(() => document?.fields.some((field) => (values[field.name] ?? "") !== field.value) ?? false, [document, values]);

  if (detail.error) {
    return (
      <div className={page.page}>
        <EmptyState
          icon={CircleAlert}
          title={detail.error.message}
          text={t.review.notFound}
          action={
            <Link href="/documentos" className="button button-secondary">
              {t.nav.documents}
            </Link>
          }
        />
      </div>
    );
  }
  if (!document) return <div className="spinner spinner-page" role="status" />;

  const apply = (next: DocumentDetail) => {
    queryClient.setQueryData(["document", documentId, reveal], next);
    setValues(valuesOf(next));
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
    void queryClient.invalidateQueries({ queryKey: ["people"] });
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const changed = Object.fromEntries(document.fields.filter((field) => (values[field.name] ?? "") !== field.value).map((field) => [field.name, values[field.name] ?? ""]));
      apply(await api.saveDocument(document.id, changed, reveal));
      toast(t.review.saved);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    } finally {
      setSaving(false);
    }
  };

  const reprocess = async () => {
    setReprocessing(true);
    try {
      apply(await api.reprocess(document.id, reveal));
      toast(t.review.reprocessed);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    } finally {
      setReprocessing(false);
    }
  };

  const remove = async () => {
    await api.deleteDocument(document.id);
    toast(t.review.deleted);
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
    void queryClient.invalidateQueries({ queryKey: ["people"] });
    router.push(document.person_id ? `/pessoas/${document.person_id}` : "/documentos");
  };

  const setValue = (name: string, value: string) => setValues((current) => ({ ...current, [name]: value }));
  const swapParents = () =>
    setValues((current) => ({ ...current, mother_name: current.father_name ?? "", father_name: current.mother_name ?? "" }));
  const extras = document.fields.filter((field) => field.section === "extra");
  const extrasFound = extras.filter((field) => field.value).length;
  const sections = [
    { key: "personal", title: t.review.personal, icon: UserRound },
    { key: "document", title: t.review.documentData, icon: IdCard },
  ];
  const holder = document.full_name || t.documents.unidentified;
  const fieldRegions = document.field_regions as Record<string, FieldRegion>;
  const selectedRegion = activeField ? fieldRegions?.[activeField] : undefined;
  const selectedSource = document.pages.find((image) => image.side === selectedRegion?.side)?.full_url;
  const nextIssue = () => {
    const candidates = document.fields.filter((field) => !values[field.name] || field.issues.length || (field.confidence ?? 0) < .9);
    const index = candidates.findIndex((field) => field.name === activeField);
    const next = candidates[(index + 1) % candidates.length];
    if (next) { setActiveField(next.name); window.document.getElementById(`field-${next.name}`)?.focus(); }
  };

  return (
    <div className={page.page}>
      <PageHead
        back={document.person_id ? { href: `/pessoas/${document.person_id}`, label: t.review.backToPerson } : { href: "/documentos", label: t.review.backToDocuments }}
        title={holder}
        description={
          <>
            {document.type_name}
            {document.type_detected && t.review.detected}
            {t.review.processedAt(format.dateTime(document.processed_at))}
          </>
        }
        actions={<StatusLabel status={document.status} />}
      />

      {document.notes.includes("cpf_corrected") && (
        <div className="alert alert-warning">
          <CircleAlert size={16} />
          {t.review.cpfCorrected}
        </div>
      )}
      {document.notes.includes("cpf_unverified") && (
        <div className="alert alert-danger">
          <CircleAlert size={16} />
          {t.review.cpfUnverified}
        </div>
      )}
      {!editable && <div className="alert alert-warning">{t.review.readOnly}</div>}
      {document.masked && can("data.reveal") && (
        <div className={styles.revealBar}>
          <span className="muted">{t.review.maskedNote}</span>
          <button className="button button-secondary" type="button" onClick={() => setReveal(true)}>
            <Eye size={16} strokeWidth={1.75} />
            {t.review.reveal}
          </button>
        </div>
      )}

      <div className={styles.review}>
        <aside className={styles.images} aria-label={t.review.images}>
          {activeField && <FieldCrop key={activeField} field={document.fields.find((field) => field.name === activeField)?.label ?? activeField} region={selectedRegion} src={selectedSource} />}
          {document.pages.map((image) => {
            const side = t.review.sides[image.side] ?? image.side;
            return (
              <button key={image.id} type="button" className={styles.imageButton} onClick={() => setViewer(image.full_url)}>
                <img src={image.thumbnail_url} alt={t.review.sideAlt(side)} />
                <span className={styles.caption}>
                  <span>{side}</span>
                  <span>{t.review.enlarge}</span>
                </span>
              </button>
            );
          })}
          {document.crops.length > 0 && (
            <div className={styles.crops}>
              {document.crops.map((image) => {
                const label = t.review.crops[image.kind] ?? image.kind;
                return (
                  <button key={image.id} type="button" className={styles.imageButton} onClick={() => setViewer(image.full_url)}>
                    <img src={image.thumbnail_url} alt={label} />
                    <span className={styles.caption}>{label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        <div className="stack">
          {document.similar_documents.length > 0 && <div className="alert alert-warning">{w.similar} {document.similar_documents.map((id) => <Link className="workflow-link" key={id} href={`/documentos/${id}`}> #{id} </Link>)}</div>}
          <div className="workflow-row"><button type="button" className="button button-secondary" onClick={nextIssue}>{w.nextIssue}</button><small>{w.shortcut}</small></div>
          <form className="panel" onSubmit={save} onFocus={(event) => {
            const name = (event.target as HTMLElement).id.replace("field-", "");
            if (document.fields.some((field) => field.name === name)) setActiveField(name);
          }} onKeyDown={(event) => {
            if (event.altKey && event.key.toLowerCase() === "n") { event.preventDefault(); nextIssue(); }
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && editable && !saving) { event.preventDefault(); event.currentTarget.requestSubmit(); }
          }}>
            <div className="panel-head">
              <h2>{t.review.formTitle}</h2>
              <span className="muted">
                {t.review.averageConfidence} <Confidence value={document.confidence} />
              </span>
            </div>
            <fieldset disabled={!editable} className={styles.fieldset}>
              {sections.map(({ key, title, icon: Icon }) => (
                <section key={key} className={styles.section}>
                  <h3>
                    <Icon size={16} strokeWidth={1.75} />
                    {title}
                  </h3>
                  <div className="form-grid">
                    {document.fields
                      .filter((field) => field.section === key)
                      .map((field) => (
                        <FieldInput key={field.name} field={field} value={values[field.name] ?? ""} onChange={setValue} />
                      ))}
                    {key === "personal" && editable && document.fields.some((field) => field.name === "mother_name") && (
                      <div className="span-2">
                        <button type="button" className="button button-ghost" onClick={swapParents}>
                          <ArrowUpDown size={14} strokeWidth={1.75} />
                          {t.review.swapParents}
                        </button>
                      </div>
                    )}
                  </div>
                </section>
              ))}
              {extras.length > 0 && (
                <details className={`${styles.section} ${styles.extras}`} open={extrasFound > 0}>
                  <summary>
                    <h3>
                      <FileSearch size={16} strokeWidth={1.75} />
                      {t.review.extras}
                      {extrasFound > 0 && ` (${extrasFound})`}
                      <ChevronDown size={16} className={styles.chevron} />
                    </h3>
                  </summary>
                  <div className="form-grid">
                    {extras.map((field) => (
                      <FieldInput key={field.name} field={field} value={values[field.name] ?? ""} onChange={setValue} />
                    ))}
                  </div>
                </details>
              )}
            </fieldset>
            {editable && (
              <div className={`panel-foot ${styles.footer}`}>
                {dirty && <span className={styles.unsaved}>{t.review.unsaved}</span>}
                <button className="button button-lg" type="submit" disabled={saving}>
                  <Save size={16} strokeWidth={1.75} />
                  {saving ? t.common.saving : t.review.confirm}
                </button>
              </div>
            )}
          </form>

          <OrganizationEditor entity="document" id={document.id} />
          <RedactionExport key={document.id} entity="document" id={document.id} pages={document.pages} />
          <section className="panel">
            <div className="panel-head">
              <h2>{t.review.processing}</h2>
            </div>
            <div className="panel-body stack">
              {(editable || can("documents.delete")) && (
                <div className="actions-row">
                  {editable && (
                    <button className="button button-secondary" type="button" onClick={reprocess} disabled={reprocessing}>
                      <RefreshCw size={16} strokeWidth={1.75} className={reprocessing ? "spin" : undefined} />
                      {reprocessing ? t.review.reprocessing : t.review.reprocess}
                    </button>
                  )}
                  {can("documents.delete") && (
                    <button className="button button-danger-ghost" type="button" onClick={() => setDeleting(true)}>
                      <Trash2 size={16} strokeWidth={1.75} />
                      {t.review.delete}
                    </button>
                  )}
                </div>
              )}
              <details>
                <summary className={`muted ${styles.rawSummary}`}>{t.review.rawText}</summary>
                <pre className={styles.raw}>{document.masked ? t.review.rawHidden : document.raw_text}</pre>
              </details>
            </div>
          </section>
        </div>
      </div>

      <DeleteDialog
        open={deleting}
        title={t.review.deleteTitle}
        description={t.review.deleteDescription(document.type_name, holder)}
        documents={1}
        images={document.image_count}
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      />
      <Lightbox src={viewer} onClose={() => setViewer(null)} />
    </div>
  );
}

type FieldInputProps = { field: Field; value: string; onChange: (name: string, value: string) => void };

function FieldInput({ field, value, onChange }: FieldInputProps) {
  const t = useT();
  const untouched = value === field.value;
  const masked = field.value.includes("*");
  const level = value && untouched ? confidenceLevel(field.confidence) : "unknown";
  const levelClass = level === "high" ? styles.high : level === "medium" ? styles.medium : level === "low" ? styles.low : "";
  const classes = [
    "field",
    WIDE_FIELDS.has(field.name) || field.kind === "multiline" ? "span-2" : "",
    level === "low" ? styles.lowField : "",
    field.issues.length ? "field-invalid" : "",
  ];
  const inputId = `field-${field.name}`;
  return (
    <div className={classes.filter(Boolean).join(" ")}>
      <label className="field-label" htmlFor={inputId}>
        {field.label}
        {value && untouched && field.confidence !== null && field.confidence !== undefined && (
          <span className={`${styles.confidence} ${levelClass}`} title={t.review.ocrConfidence}>
            {formatPercent(field.confidence)}
          </span>
        )}
        {value && !untouched && <span className={styles.confidence}>{t.review.edited}</span>}
      </label>
      {field.kind === "multiline" ? (
        <textarea
          id={inputId}
          rows={3}
          className="mono"
          value={value}
          maxLength={2000}
          readOnly={masked}
          onChange={(event) => onChange(field.name, event.target.value)}
        />
      ) : (
        <input
          id={inputId}
          value={value}
          maxLength={200}
          readOnly={masked}
          onChange={(event) => onChange(field.name, event.target.value)}
          inputMode={field.kind === "date" || field.kind === "cpf" ? "numeric" : undefined}
          placeholder={field.kind === "date" ? "dd/mm/aaaa" : field.kind === "cpf" ? "000.000.000-00" : undefined}
          className={field.kind === "cpf" ? "mono" : undefined}
          aria-invalid={field.issues.length > 0 || undefined}
        />
      )}
      {field.issues.map((issue) => (
        <span key={issue} className="field-error">
          {issue}
        </span>
      ))}
    </div>
  );
}
