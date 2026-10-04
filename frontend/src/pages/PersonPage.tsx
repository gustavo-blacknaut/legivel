import { ArrowLeft, CircleAlert, CircleCheck, FilePlus2, Pencil, Save, ShieldCheck, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { DeleteDialog } from "../components/DeleteDialog";
import { EmptyState } from "../components/ListState";
import { Confidence, StatusLabel } from "../components/Status";
import { useToast } from "../components/Toast";
import { DOCUMENT_TYPE_LABELS, formatCpf, formatDateTime } from "../format";
import type { PersonDetail, Verification } from "../types";

const EDITABLE_FIELDS: { name: keyof PersonDetail; label: string; wide?: boolean; placeholder?: string; mono?: boolean }[] = [
  { name: "full_name", label: "Nome completo", wide: true },
  { name: "cpf", label: "CPF", placeholder: "000.000.000-00", mono: true },
  { name: "birth_date", label: "Data de nascimento", placeholder: "dd/mm/aaaa" },
  { name: "birthplace", label: "Naturalidade" },
  { name: "mother_name", label: "Mãe", wide: true },
  { name: "father_name", label: "Pai", wide: true },
];

function formValues(person: PersonDetail): Record<string, string> {
  return {
    full_name: person.full_name ?? "",
    cpf: formatCpf(person.cpf),
    birth_date: person.birth_date ?? "",
    birthplace: person.birthplace ?? "",
    mother_name: person.mother_name ?? "",
    father_name: person.father_name ?? "",
  };
}

export function PersonPage() {
  const personId = Number(useParams().id);
  const navigate = useNavigate();
  const toast = useToast();
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [verification, setVerification] = useState<Verification | null>(null);

  useEffect(() => {
    api.person(personId).then(setPerson).catch((caught) => setError(caught.message));
  }, [personId]);

  if (error) {
    return (
      <div className="page">
        <EmptyState icon={CircleAlert} title={error} text="O cadastro pode ter sido apagado." action={<Link to="/pessoas" className="button button-secondary">Ver pessoas</Link>} />
      </div>
    );
  }
  if (!person) return <div className="spinner spinner-page" />;

  const startEditing = () => {
    setValues(formValues(person));
    setFormError(null);
    setEditing(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      setPerson(await api.updatePerson(person.id, values));
      setEditing(false);
      toast("Dados atualizados.");
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    try {
      const result = await api.verifyPerson(person.id);
      setPerson(result.person);
      setVerification(result);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Não foi possível verificar.", "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    await api.deletePerson(person.id);
    toast(`${person.full_name ?? "Pessoa"} apagada.`);
    navigate("/pessoas");
  };

  const details: [string, string | null][] = [
    ["CPF", formatCpf(person.cpf)],
    ["Nascimento", person.birth_date],
    ["Naturalidade", person.birthplace],
    ["Mãe", person.mother_name],
    ["Pai", person.father_name],
    ["Cadastro", formatDateTime(person.created_at, true)],
    ["Última atualização", formatDateTime(person.updated_at, true)],
  ];

  return (
    <div className="page">
      <PageHead
        back={
          <Link to="/pessoas" className="breadcrumb">
            <ArrowLeft size={14} />
            Pessoas
          </Link>
        }
        title={person.full_name || "Sem nome"}
        description={<StatusLabel status={person.status} />}
        actions={
          <div className="actions-row">
            <button className="button button-secondary" type="button" onClick={verify} disabled={busy}>
              <ShieldCheck size={16} strokeWidth={1.75} />
              Verificar
            </button>
            <Link to="/novo" className="button button-secondary">
              <FilePlus2 size={16} strokeWidth={1.75} />
              Adicionar documento
            </Link>
            <button className="button button-danger-ghost" type="button" onClick={() => setDeleting(true)}>
              <Trash2 size={16} strokeWidth={1.75} />
              Apagar
            </button>
          </div>
        }
      />

      {verification && (
        <section className={`verification ${verification.problems.length ? "has-problems" : "is-ok"}`} aria-live="polite">
          <div className="verification-head">
            {verification.problems.length ? <CircleAlert size={18} /> : <CircleCheck size={18} />}
            <strong>
              {verification.problems.length
                ? `Verificação concluída com ${verification.problems.length} pendência(s)`
                : "Verificação concluída sem pendências"}
            </strong>
            <button className="icon-button" type="button" aria-label="Fechar resultado" onClick={() => setVerification(null)}>
              <X size={16} />
            </button>
          </div>
          {verification.changes.length > 0 && (
            <ul>
              {verification.changes.map((change) => (
                <li key={change}>Corrigido: {change}</li>
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

      <div className="person-grid">
        <div className="stack">
          <section className="panel">
            <div className="panel-head">
              <h2>Dados consolidados</h2>
              {!editing && (
                <button className="button button-ghost" type="button" onClick={startEditing}>
                  <Pencil size={14} strokeWidth={1.75} />
                  Editar
                </button>
              )}
            </div>
            {editing ? (
              <form onSubmit={save}>
                <div className="panel-body form-grid">
                  {EDITABLE_FIELDS.map((field) => (
                    <div key={field.name} className={`field${field.wide ? " span-2" : ""}`}>
                      <label className="field-label" htmlFor={`person-${field.name}`}>
                        {field.label}
                      </label>
                      <input
                        id={`person-${field.name}`}
                        value={values[field.name] ?? ""}
                        placeholder={field.placeholder}
                        className={field.mono ? "mono" : undefined}
                        onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
                      />
                    </div>
                  ))}
                  {formError && <p className="field-error span-2">{formError}</p>}
                  <p className="muted flush span-2">Os valores são gravados em maiúsculas e sem acentos, como nos documentos.</p>
                </div>
                <div className="form-footer">
                  <button className="button button-secondary" type="button" onClick={() => setEditing(false)} disabled={busy}>
                    Cancelar
                  </button>
                  <button className="button" type="submit" disabled={busy}>
                    <Save size={16} strokeWidth={1.75} />
                    Salvar dados
                  </button>
                </div>
              </form>
            ) : (
              <dl className="meta-list panel-body">
                {details.map(([label, value]) => (
                  <div key={label} className="contents">
                    <dt>{label}</dt>
                    <dd className={label === "CPF" ? "mono" : undefined}>{value || "—"}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Outros dados</h2>
              <span className="muted">{person.other_data.length} informação(ões)</span>
            </div>
            {person.other_data.length === 0 ? (
              <p className="panel-body muted flush">Nenhuma informação adicional encontrada nos documentos.</p>
            ) : (
              <dl className="meta-list panel-body">
                {person.other_data.map((item) => (
                  <div key={`${item.label}-${item.value}`} className="contents">
                    <dt>{item.label}</dt>
                    <dd>
                      {item.value}{" "}
                      <Link className="source-link" to={`/documentos/${item.document_id}`}>
                        {DOCUMENT_TYPE_LABELS[item.doc_type] ?? item.doc_type.toUpperCase()} #{item.document_id}
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
            <h2>Documentos ({person.documents})</h2>
          </div>
          <table className="table table-auto">
            <tbody>
              {person.document_list.map((document) => (
                <tr key={document.id} onClick={() => navigate(`/documentos/${document.id}`)}>
                  <td className="cell-primary">
                    <Link to={`/documentos/${document.id}`} className="cell-name" onClick={(event) => event.stopPropagation()}>
                      {document.thumbnail_url ? <img className="thumb" src={document.thumbnail_url} alt="" /> : <span className="thumb" />}
                      <span>{DOCUMENT_TYPE_LABELS[document.doc_type] ?? document.doc_type.toUpperCase()}</span>
                    </Link>
                  </td>
                  <td className="cell-meta"><Confidence value={document.confidence} /></td>
                  <td className="cell-meta"><StatusLabel status={document.status} /></td>
                  <td className="cell-meta col-optional">{formatDateTime(document.processed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
      <DeleteDialog
        open={deleting}
        title="Apagar pessoa e documentos"
        description={
          <>
            <strong>{person.full_name ?? "Esta pessoa"}</strong> será removida do cadastro junto com tudo o que está vinculado a ela.
          </>
        }
        documents={person.documents}
        images={person.images}
        confirmationValues={[person.full_name ?? "", person.cpf ?? ""]}
        confirmationLabel="Para confirmar, digite o nome completo ou o CPF"
        onConfirm={remove}
        onClose={() => setDeleting(false)}
      />
    </div>
  );
}
