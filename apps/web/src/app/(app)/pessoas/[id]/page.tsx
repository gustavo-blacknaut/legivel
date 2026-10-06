"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Download, Eye, FilePlus2, Pencil, Save, ShieldCheck, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { DeleteDialog } from "@/components/DeleteDialog";
import { documentTypeLabel } from "@/components/ListFilters";
import { EmptyState } from "@/components/ListState";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import styles from "@/components/Review.module.css";
import { Confidence, StatusLabel } from "@/components/Status";
import { useToast } from "@/components/Toast";
import { api, type PersonDetail, type Verification } from "@/lib/api/endpoints";
import { formatCpf } from "@/lib/format";
import { optionalCpf, optionalDate, requiredText, validate, type FieldErrors } from "@/lib/forms";
import { useLocale } from "@/lib/i18n";
import { useSession } from "@/lib/session";

const EDITABLE = ["full_name", "cpf", "birth_date", "birthplace", "mother_name", "father_name"] as const;
type EditableName = (typeof EDITABLE)[number];
const WIDE = new Set<EditableName>(["full_name", "mother_name", "father_name"]);

function formValues(person: PersonDetail): Record<EditableName, string> {
  return {
    full_name: person.full_name ?? "",
    cpf: formatCpf(person.cpf),
    birth_date: person.birth_date ?? "",
    birthplace: person.birthplace ?? "",
    mother_name: person.mother_name ?? "",
    father_name: person.father_name ?? "",
  };
}

export default function PersonPage() {
  const { t, format } = useLocale();
  const { can } = useSession();
  const personId = Number(useParams<{ id: string }>().id);
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [reveal, setReveal] = useState(false);
  const query = useQuery({
    queryKey: ["person", personId, reveal],
    queryFn: () => api.person(personId, reveal),
    enabled: Number.isFinite(personId),
  });
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<Record<EditableName, string>>(formValues({} as PersonDetail));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [verification, setVerification] = useState<Verification | null>(null);
  const person = query.data;

  if (query.error) {
    return (
      <div className={page.page}>
        <EmptyState
          icon={CircleAlert}
          title={query.error.message}
          text={t.person.notFound}
          action={
            <Link href="/pessoas" className="button button-secondary">
              {t.person.viewPeople}
            </Link>
          }
        />
      </div>
    );
  }
  if (!person) return <div className="spinner spinner-page" role="status" />;

  const schema = z.object({
    full_name: requiredText(t, 200),
    cpf: optionalCpf(t),
    birth_date: optionalDate(t),
    birthplace: z.string().trim().max(120, t.validation.tooLong(120)),
    mother_name: z.string().trim().max(200, t.validation.tooLong(200)),
    father_name: z.string().trim().max(200, t.validation.tooLong(200)),
  });

  const update = (next: PersonDetail) => {
    queryClient.setQueryData(["person", personId, reveal], next);
    void queryClient.invalidateQueries({ queryKey: ["people"] });
  };

  const startEditing = () => {
    setValues(formValues(person));
    setErrors({});
    setFormError(null);
    setEditing(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(schema, values);
    if (!result.ok) {
      setErrors(result.errors);
      return;
    }
    setErrors({});
    setBusy(true);
    setFormError(null);
    try {
      update(await api.updatePerson(person.id, result.data, reveal));
      setEditing(false);
      toast(t.person.updated);
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : t.common.error);
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    try {
      const result = await api.verifyPerson(person.id, reveal);
      update(result.person);
      setVerification(result);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    } finally {
      setBusy(false);
    }
  };

  const exportData = async () => {
    setBusy(true);
    try {
      const blob = await api.exportPerson(person.id);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `pessoa-${person.id}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      toast(t.person.exported);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    await api.deletePerson(person.id);
    toast(t.people.deleted(person.full_name ?? t.people.fallbackName));
    void queryClient.invalidateQueries({ queryKey: ["people"] });
    router.push("/pessoas");
  };

  const details: [string, string | null | undefined, boolean?][] = [
    [t.person.fields.cpf, formatCpf(person.cpf), true],
    [t.person.fields.birth_date, person.birth_date],
    [t.person.fields.birthplace, person.birthplace],
    [t.person.fields.mother_name, person.mother_name],
    [t.person.fields.father_name, person.father_name],
    [t.person.fields.created, format.dateTime(person.created_at, true)],
    [t.person.fields.updated, format.dateTime(person.updated_at, true)],
  ];
  const editor = can("people.edit");

  return (
    <div className={page.page}>
      <PageHead
        back={{ href: "/pessoas", label: t.person.back }}
        title={person.full_name || t.people.unnamed}
        description={<StatusLabel status={person.status} />}
        actions={
          <>
            {editor && (
              <button className="button button-secondary" type="button" onClick={verify} disabled={busy}>
                <ShieldCheck size={16} strokeWidth={1.75} />
                {t.person.verify}
              </button>
            )}
            {can("documents.upload") && (
              <Link href="/novo" className="button button-secondary">
                <FilePlus2 size={16} strokeWidth={1.75} />
                {t.person.addDocument}
              </Link>
            )}
            {can("data.reveal") && (
              <button className="button button-secondary" type="button" onClick={exportData} disabled={busy}>
                <Download size={16} strokeWidth={1.75} />
                {t.person.export}
              </button>
            )}
            {can("people.delete") && (
              <button className="button button-danger-ghost" type="button" onClick={() => setDeleting(true)}>
                <Trash2 size={16} strokeWidth={1.75} />
                {t.person.delete}
              </button>
            )}
          </>
        }
      />

      {verification && (
        <section className={`${styles.verification} ${verification.problems.length ? styles.problems : styles.ok}`} aria-live="polite">
          <div className={styles.verificationHead}>
            {verification.problems.length ? <CircleAlert size={18} /> : <CircleCheck size={18} />}
            <strong>{verification.problems.length ? t.person.verificationProblems(verification.problems.length) : t.person.verificationOk}</strong>
            <button className="icon-button" type="button" aria-label={t.person.closeResult} onClick={() => setVerification(null)}>
              <X size={16} />
            </button>
          </div>
          {verification.changes.length > 0 && (
            <ul>
              {verification.changes.map((change) => (
                <li key={change}>{t.person.corrected(change)}</li>
              ))}
            </ul>
          )}
          {verification.problems.length > 0 && (
            <ul>
              {verification.problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className={page.columns}>
        <div className="stack">
          <section className="panel">
            <div className="panel-head">
              <h2>{t.person.consolidated}</h2>
              {person.masked && can("data.reveal") && (
                <button className="button button-ghost" type="button" onClick={() => setReveal(true)}>
                  <Eye size={14} strokeWidth={1.75} />
                  {t.review.reveal}
                </button>
              )}
              {editor && !editing && (
                <button className="button button-ghost" type="button" onClick={startEditing}>
                  <Pencil size={14} strokeWidth={1.75} />
                  {t.common.edit}
                </button>
              )}
            </div>
            {editing ? (
              <form onSubmit={save} noValidate>
                <div className="panel-body form-grid">
                  {EDITABLE.map((name) => (
                    <div key={name} className={`field ${WIDE.has(name) ? "span-2" : ""} ${errors[name] ? "field-invalid" : ""}`}>
                      <label className="field-label" htmlFor={`person-${name}`}>
                        {t.person.fields[name]}
                      </label>
                      <input
                        id={`person-${name}`}
                        value={values[name]}
                        placeholder={name === "cpf" ? "000.000.000-00" : name === "birth_date" ? "dd/mm/aaaa" : undefined}
                        inputMode={name === "cpf" || name === "birth_date" ? "numeric" : undefined}
                        readOnly={name === "cpf" && person.masked}
                        className={name === "cpf" ? "mono" : undefined}
                        aria-invalid={Boolean(errors[name]) || undefined}
                        onChange={(event) => setValues((current) => ({ ...current, [name]: event.target.value }))}
                      />
                      {errors[name] && <span className="field-error">{errors[name]}</span>}
                    </div>
                  ))}
                  {formError && <p className="field-error span-2">{formError}</p>}
                  <p className="muted flush span-2">{t.person.upperNote}</p>
                </div>
                <div className="panel-foot">
                  <button className="button button-secondary" type="button" onClick={() => setEditing(false)} disabled={busy}>
                    {t.common.cancel}
                  </button>
                  <button className="button" type="submit" disabled={busy}>
                    <Save size={16} strokeWidth={1.75} />
                    {t.person.saveData}
                  </button>
                </div>
              </form>
            ) : (
              <dl className="meta-list panel-body">
                {details.map(([label, value, mono]) => (
                  <div key={label} className="contents">
                    <dt>{label}</dt>
                    <dd className={mono ? "mono" : undefined}>{value || "—"}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>{t.person.otherData}</h2>
              <span className="muted">{t.person.otherCount(person.other_data.length)}</span>
            </div>
            {person.other_data.length === 0 ? (
              <p className="panel-body muted flush">{t.person.otherEmpty}</p>
            ) : (
              <dl className="meta-list panel-body">
                {person.other_data.map((item) => (
                  <div key={`${item.label}-${item.value}`} className="contents">
                    <dt>{item.label}</dt>
                    <dd>
                      {item.value}{" "}
                      <Link className={styles.source} href={`/documentos/${item.document_id}`}>
                        {documentTypeLabel(item.doc_type)} #{item.document_id}
                      </Link>
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        </div>

        <section className="panel">
          <div className="panel-head">
            <h2>{t.person.documentsTitle(person.documents)}</h2>
          </div>
          <table className={`${page.table} ${page.clickable} ${page.auto}`}>
            <tbody>
              {person.document_list.map((document) => (
                <tr key={document.id} onClick={() => router.push(`/documentos/${document.id}`)}>
                  <td className={page.primary}>
                    <Link href={`/documentos/${document.id}`} className={page.name} onClick={(event) => event.stopPropagation()}>
                      {document.thumbnail_url ? <img className={page.thumb} src={document.thumbnail_url} alt="" /> : <span className={page.thumb} />}
                      <span>{documentTypeLabel(document.doc_type)}</span>
                    </Link>
                  </td>
                  <td className={page.meta}>
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
        </section>
      </div>
      <DeleteDialog
        open={deleting}
        title={t.people.deleteTitle}
        description={t.people.deleteDescription(person.full_name ?? t.people.fallbackName)}
        documents={person.documents}
        images={person.images}
        confirmationValues={[person.full_name ?? "", person.cpf ?? ""]}
        confirmationLabel={t.people.deleteConfirm}
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      />
    </div>
  );
}
