import {
  ArrowLeft,
  ArrowUpDown,
  ChevronDown,
  CircleAlert,
  FileSearch,
  IdCard,
  RefreshCw,
  Save,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { DeleteDialog } from "../components/DeleteDialog";
import { EmptyState } from "../components/ListState";
import { Confidence, StatusLabel } from "../components/Status";
import { useToast } from "../components/Toast";
import { confidenceLevel, formatDateTime, formatPercent } from "../format";
import type { DocumentDetail, DocumentType, Field, FieldSection, ImageInfo } from "../types";

const SIDE_LABELS: Record<string, string> = { front: "Frente", back: "Verso", open: "Frente" };
const CROP_LABELS: Record<string, string> = { portrait: "Foto", signature: "Assinatura", fingerprint: "Polegar" };
const SECTIONS: { key: FieldSection; title: string; icon: typeof UserRound }[] = [
  { key: "personal", title: "Dados pessoais", icon: UserRound },
  { key: "document", title: "Dados do documento", icon: IdCard },
];
const WIDE_FIELDS = new Set(["full_name", "mother_name", "father_name", "mrz_raw", "civil_registry"]);

export function DocumentPage() {
  const documentId = Number(useParams().id);
  const navigate = useNavigate();
  const toast = useToast();
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [types, setTypes] = useState<DocumentType[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessType, setReprocessType] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [viewer, setViewer] = useState<ImageInfo | null>(null);

  const load = useCallback((detail: DocumentDetail) => {
    setDocument(detail);
    setValues(Object.fromEntries(detail.fields.map((field) => [field.name, field.value])));
  }, []);

  useEffect(() => {
    api.document(documentId).then(load).catch((caught) => setError(caught.message));
    api.documentTypes().then(setTypes).catch(() => undefined);
  }, [documentId, load]);

  useEffect(() => {
    if (!viewer) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setViewer(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [viewer]);

  const dirty = useMemo(
    () => document?.fields.some((field) => (values[field.name] ?? "") !== field.value) ?? false,
    [document, values],
  );

  if (error) {
    return (
      <div className="page">
        <EmptyState
          icon={CircleAlert}
          title={error}
          text="O documento pode ter sido apagado."
          action={<Link to="/documentos" className="button button-secondary">Ver documentos</Link>}
        />
      </div>
    );
  }

  if (!document) return <div className="spinner spinner-page" />;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      load(await api.saveDocument(document.id, values));
      toast("Revisão salva.");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Falha ao salvar.", "error");
    } finally {
      setSaving(false);
    }
  };

  const reprocess = async () => {
    setReprocessing(true);
    try {
      load(await api.reprocess(document.id, reprocessType || null));
      toast("Documento reprocessado.");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Falha ao reprocessar.", "error");
    } finally {
      setReprocessing(false);
    }
  };

  const remove = async () => {
    await api.deleteDocument(document.id);
    toast("Documento apagado.");
    navigate(document.person_id ? `/pessoas/${document.person_id}` : "/documentos");
  };

  const setValue = (name: string, value: string) => setValues((current) => ({ ...current, [name]: value }));
  const swapParents = () =>
    setValues((current) => ({ ...current, mother_name: current.father_name ?? "", father_name: current.mother_name ?? "" }));
  const extraFields = document.fields.filter((field) => field.section === "extra");
  const extraFound = extraFields.filter((field) => field.value).length;

  return (
    <div className="page">
      <PageHead
        back={
          <Link to={document.person_id ? `/pessoas/${document.person_id}` : "/documentos"} className="breadcrumb">
            <ArrowLeft size={14} />
            {document.person_id ? "Voltar para a pessoa" : "Documentos"}
          </Link>
        }
        title={document.full_name || "Titular não identificado"}
        description={
          <>
            {document.type_name}
            {document.type_detected && " · identificado automaticamente"} · processado em {formatDateTime(document.processed_at)}
          </>
        }
        actions={<StatusLabel status={document.status} />}
      />

      {document.notes.includes("cpf_corrected") && (
        <div className="alert alert-warning">
          <CircleAlert size={16} />O CPF lido não passava no dígito verificador e foi corrigido após uma nova leitura. Confira antes de salvar.
        </div>
      )}
      {document.notes.includes("cpf_unverified") && (
        <div className="alert alert-danger">
          <CircleAlert size={16} />O CPF lido não passa no dígito verificador. Corrija manualmente.
        </div>
      )}

      <div className="review">
        <aside className="review-images" aria-label="Imagens do documento">
          {document.pages.map((image) => (
            <button key={image.id} type="button" className="image-button" onClick={() => setViewer(image)}>
              <img src={image.thumbnail_url} alt={`${SIDE_LABELS[image.side] ?? image.side} do documento`} />
              <span className="image-caption">
                <span>{SIDE_LABELS[image.side] ?? image.side}</span>
                <span>Ampliar</span>
              </span>
            </button>
          ))}
          {document.crops.length > 0 && (
            <div className="crops">
              {document.crops.map((image) => (
                <button key={image.id} type="button" className="image-button" onClick={() => setViewer(image)}>
                  <img src={image.thumbnail_url} alt={CROP_LABELS[image.kind] ?? image.kind} />
                  <span className="image-caption">{CROP_LABELS[image.kind] ?? image.kind}</span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <div className="stack">
          <form className="panel" onSubmit={save}>
            <div className="panel-head">
              <h2>Revisão dos dados</h2>
              <span className="muted">
                Confiança média <Confidence value={document.confidence} />
              </span>
            </div>
            {SECTIONS.map(({ key, title, icon: Icon }) => (
              <section key={key} className="form-section">
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
                  {key === "personal" && document.fields.some((field) => field.name === "mother_name") && (
                    <div className="span-2">
                      <button type="button" className="button button-ghost" onClick={swapParents}>
                        <ArrowUpDown size={14} strokeWidth={1.75} />
                        Trocar pai e mãe
                      </button>
                    </div>
                  )}
                </div>
              </section>
            ))}
            {extraFields.length > 0 && (
              <details className="form-section extras" open={extraFound > 0}>
                <summary>
                  <h3>
                    <FileSearch size={16} strokeWidth={1.75} />
                    Outras informações{extraFound > 0 && ` (${extraFound})`}
                    <ChevronDown size={16} className="chevron" />
                  </h3>
                </summary>
                <div className="form-grid">
                  {extraFields.map((field) => (
                    <FieldInput key={field.name} field={field} value={values[field.name] ?? ""} onChange={setValue} />
                  ))}
                </div>
              </details>
            )}
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
              <h2>Processamento</h2>
            </div>
            <div className="panel-body stack">
              <div className="actions-row">
                <label className="field grow">
                  <span className="field-label">Reprocessar como</span>
                  <select value={reprocessType} onChange={(event) => setReprocessType(event.target.value)}>
                    <option value="">Identificar automaticamente</option>
                    {types.map((type) => (
                      <option key={type.doc_type} value={type.doc_type}>
                        {type.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="button button-secondary" type="button" onClick={reprocess} disabled={reprocessing}>
                  <RefreshCw size={16} strokeWidth={1.75} className={reprocessing ? "spin" : undefined} />
                  {reprocessing ? "Reprocessando…" : "Reprocessar OCR"}
                </button>
                <button className="button button-danger-ghost" type="button" onClick={() => setDeleting(true)}>
                  <Trash2 size={16} strokeWidth={1.75} />
                  Apagar documento
                </button>
              </div>
              <details>
                <summary className="muted">Texto reconhecido pelo OCR</summary>
                <pre className="raw">{document.raw_text}</pre>
              </details>
            </div>
          </section>
        </div>
      </div>

      <DeleteDialog
        open={deleting}
        title="Apagar documento"
        description={
          <>
            O {document.type_name} de <strong>{document.full_name || "titular não identificado"}</strong> será apagado.
          </>
        }
        documents={1}
        images={document.image_count}
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      />

      {viewer && (
        <div className="lightbox" onClick={() => setViewer(null)} role="dialog" aria-label="Imagem ampliada">
          <button className="icon-button" type="button" aria-label="Fechar" autoFocus>
            <X size={20} />
          </button>
          <img src={viewer.full_url} alt="" onClick={(event) => event.stopPropagation()} />
        </div>
      )}
    </div>
  );
}

type FieldInputProps = {
  field: Field;
  value: string;
  onChange: (name: string, value: string) => void;
};

function FieldInput({ field, value, onChange }: FieldInputProps) {
  const untouched = value === field.value;
  const level = value && untouched ? confidenceLevel(field.confidence) : "unknown";
  const classes = ["field", WIDE_FIELDS.has(field.name) || field.kind === "multiline" ? "span-2" : "", `field-${level}`, field.issues.length ? "field-invalid" : ""];
  const inputId = `field-${field.name}`;
  return (
    <div className={classes.filter(Boolean).join(" ")}>
      <label className="field-label" htmlFor={inputId}>
        {field.label}
        {value && untouched && field.confidence !== null && (
          <span className={`field-confidence ${level}`} title="Confiança do OCR">
            {formatPercent(field.confidence)}
          </span>
        )}
        {value && !untouched && <span className="field-confidence">editado</span>}
      </label>
      {field.kind === "multiline" ? (
        <textarea id={inputId} rows={3} className="mono" value={value} onChange={(event) => onChange(field.name, event.target.value)} />
      ) : (
        <input
          id={inputId}
          value={value}
          onChange={(event) => onChange(field.name, event.target.value)}
          inputMode={field.kind === "date" || field.kind === "cpf" ? "numeric" : undefined}
          placeholder={field.kind === "date" ? "dd/mm/aaaa" : field.kind === "cpf" ? "000.000.000-00" : undefined}
          className={field.kind === "cpf" ? "mono" : undefined}
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
