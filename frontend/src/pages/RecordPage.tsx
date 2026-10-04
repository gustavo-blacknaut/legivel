import { ArrowLeft, CircleAlert, CreditCard, Download, Lock, Save, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { DeleteDialog } from "../components/DeleteDialog";
import { EmptyState } from "../components/ListState";
import { Confidence, StatusLabel } from "../components/Status";
import { useToast } from "../components/Toast";
import { confidenceLevel, formatDateTime, formatPercent } from "../format";
import type { RecordDetail, RecordPageInfo } from "../types";

const EXPORT_LABELS: Record<string, string> = { pdf: "PDF pesquisável", txt: "Texto (TXT)", md: "Markdown" };
const LANGUAGE_NAMES: Record<string, string> = {
  pt: "Português", en: "Inglês", es: "Espanhol", fr: "Francês", de: "Alemão", it: "Italiano",
  ru: "Russo", zh: "Chinês", ja: "Japonês", ko: "Coreano", ar: "Árabe", hi: "Hindi",
};
const READ_ONLY_KINDS = new Set(["readonly", "masked"]);

export function RecordPage() {
  const recordId = Number(useParams().id);
  const navigate = useNavigate();
  const toast = useToast();
  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [viewer, setViewer] = useState<RecordPageInfo | null>(null);

  const load = (detail: RecordDetail) => {
    setRecord(detail);
    setValues(Object.fromEntries(detail.fields.map((field) => [field.name, field.value])));
  };

  useEffect(() => {
    api.record(recordId).then(load).catch((caught) => setError(caught.message));
  }, [recordId]);

  const dirty = useMemo(() => record?.fields.some((field) => (values[field.name] ?? "") !== field.value) ?? false, [record, values]);

  if (error) {
    return (
      <div className="page">
        <EmptyState icon={CircleAlert} title={error} text="O registro pode ter sido apagado." action={<Link to="/busca" className="button button-secondary">Voltar à busca</Link>} />
      </div>
    );
  }
  if (!record) return <div className="spinner spinner-page" />;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      load(await api.reviewRecord(record.id, values));
      toast("Revisão salva.");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Falha ao salvar.", "error");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    await api.deleteRecord(record.id);
    toast("Registro apagado.");
    navigate(`/modulos/${record.module}`);
  };

  const pageText = record.pages.map((page) => page.text).filter(Boolean);

  return (
    <div className="page">
      <PageHead
        back={
          <Link to={`/modulos/${record.module}`} className="breadcrumb">
            <ArrowLeft size={14} />
            {record.module_name}
          </Link>
        }
        title={record.title || "Sem título"}
        description={
          <>
            {record.kind_label ?? record.module_name}
            {record.language && ` · ${LANGUAGE_NAMES[record.language] ?? record.language}`}
            {` · processado em ${formatDateTime(record.created_at)}`}
          </>
        }
        actions={<StatusLabel status={record.status} />}
      />

      {record.issues.length > 0 && (
        <div className="alert alert-warning">
          <CircleAlert size={16} />
          <span>{record.issues.map((issue) => issue.message).join(" · ")}</span>
        </div>
      )}

      <div className={record.pages.length ? "review" : "single-column"}>
        {record.pages.length > 0 && (
          <aside className="review-images" aria-label="Páginas">
            <div className="page-grid">
              {record.pages.map((page) => (
                <button key={page.id} type="button" className="image-button" onClick={() => setViewer(page)}>
                  {page.thumbnail_url && <img src={page.thumbnail_url} alt={`Página ${page.number}`} />}
                  <span className="image-caption">
                    <span>Página {page.number}</span>
                    {page.columns && page.columns > 1 && <span>{page.columns} colunas</span>}
                  </span>
                </button>
              ))}
            </div>
          </aside>
        )}

        <div className="stack">
          {record.card && (
            <section className="panel card-panel">
              <div className="card-visual" aria-label="Cartão mascarado">
                <span className="card-brand">
                  <CreditCard size={18} strokeWidth={1.5} />
                  {record.card.brand ?? "Bandeira não identificada"}
                </span>
                <span className="card-number mono">•••• •••• •••• {record.card.last4 ?? "????"}</span>
                <span className="card-meta">
                  <span>{record.card.holder_name ?? "Nome não lido"}</span>
                  <span className="mono">{record.card.expiry ?? "--/--"}</span>
                </span>
              </div>
              <p className="panel-body muted flush card-note">
                <Lock size={14} strokeWidth={1.75} />
                {record.card.number_stored
                  ? "O número completo está guardado criptografado com chave própria e nunca é exibido."
                  : "Somente os 4 últimos dígitos e a bandeira foram guardados. O CVV nunca é lido."}
              </p>
            </section>
          )}

          <form className="panel" onSubmit={save}>
            <div className="panel-head">
              <h2>Dados extraídos</h2>
              <span className="muted">
                Confiança <Confidence value={record.confidence} />
              </span>
            </div>
            <div className="panel-body form-grid">
              {record.fields.map((field) => {
                const value = values[field.name] ?? "";
                const untouched = value === field.value;
                const level = value && untouched ? confidenceLevel(field.confidence) : "unknown";
                const readOnly = READ_ONLY_KINDS.has(field.kind);
                const wide = value.length > 40 || ["title", "address", "digitable_line", "access_key", "main_activity"].includes(field.name);
                return (
                  <div key={field.name} className={`field field-${level}${wide ? " span-2" : ""}${field.issues.length ? " field-invalid" : ""}`}>
                    <label className="field-label" htmlFor={`record-${field.name}`}>
                      {field.label}
                      {value && untouched && field.confidence !== null && !readOnly && (
                        <span className={`field-confidence ${level}`}>{formatPercent(field.confidence)}</span>
                      )}
                    </label>
                    <input
                      id={`record-${field.name}`}
                      value={value}
                      readOnly={readOnly}
                      className={["digitable_line", "access_key", "masked_number"].includes(field.name) ? "mono" : undefined}
                      onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
                    />
                    {field.issues.map((issue) => (
                      <span key={issue} className="field-error">
                        {issue}
                      </span>
                    ))}
                  </div>
                );
              })}
            </div>
            <div className="form-footer">
              {dirty && <span className="unsaved">Alterações não salvas</span>}
              <button className="button" type="submit" disabled={saving}>
                <Save size={16} strokeWidth={1.75} />
                {saving ? "Salvando…" : "Confirmar revisão"}
              </button>
            </div>
          </form>

          <section className="panel">
            <div className="panel-head">
              <h2>Ações</h2>
            </div>
            <div className="panel-body stack">
              <div className="actions-row">
                {record.exports.map((type) => (
                  <a key={type} className="button button-secondary" href={`/api/records/${record.id}/export/${type}`} download>
                    <Download size={16} strokeWidth={1.75} />
                    {EXPORT_LABELS[type] ?? type.toUpperCase()}
                  </a>
                ))}
                <button className="button button-danger-ghost" type="button" onClick={() => setDeleting(true)}>
                  <Trash2 size={16} strokeWidth={1.75} />
                  Apagar registro
                </button>
              </div>
              {pageText.length > 0 && (
                <details>
                  <summary className="muted">Texto reconhecido ({record.page_count} página(s))</summary>
                  <pre className="raw">{pageText.join("\n\n— — —\n\n")}</pre>
                </details>
              )}
            </div>
          </section>
        </div>
      </div>

      <DeleteDialog
        open={deleting}
        title="Apagar registro"
        description={
          <>
            <strong>{record.title || "Este registro"}</strong> e todas as imagens dele serão apagados.
          </>
        }
        documents={1}
        images={record.pages.length}
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      />

      {viewer?.full_url && (
        <div className="lightbox" onClick={() => setViewer(null)} role="dialog" aria-label="Página ampliada">
          <button className="icon-button" type="button" aria-label="Fechar" autoFocus>
            <X size={20} />
          </button>
          <img src={viewer.full_url} alt="" onClick={(event) => event.stopPropagation()} />
        </div>
      )}
    </div>
  );
}
