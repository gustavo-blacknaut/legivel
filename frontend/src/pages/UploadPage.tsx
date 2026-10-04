import { Check, ScanText, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { Dropzone } from "../components/Dropzone";
import { ScanLinks } from "../components/ScanLinks";

const CHECKLIST = [
  "Documento inteiro na foto, sem cortar as bordas",
  "Sem reflexo ou sombra sobre o texto",
  "Em pé ou deitado: a orientação é corrigida automaticamente",
];

export function UploadPage() {
  const navigate = useNavigate();
  const [front, setFront] = useState<File | null>(null);
  const [back, setBack] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const form = new FormData();
    if (front) form.append("front", front);
    if (back) form.append("back", back);
    setBusy(true);
    setError(null);
    try {
      const document = await api.upload(form);
      navigate(`/documentos/${document.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao enviar.");
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <PageHead title="Novo documento" description="RG, CNH ou cartão CPF. O tipo é identificado automaticamente." />
      <div className="upload-stack">
        <form className="panel narrow" onSubmit={submit}>
          <div className="panel-body">
            {error && <div className="alert alert-danger">{error}</div>}
            <div className="upload">
              <Dropzone label="Frente" hint="Tirar foto ou escolher arquivo" file={front} onChange={setFront} />
              <Dropzone label="Verso" hint="Tirar foto ou escolher arquivo" file={back} onChange={setBack} />
            </div>
            <ul className="checklist">
              {CHECKLIST.map((item) => (
                <li key={item}>
                  <Check size={16} strokeWidth={2} />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="form-footer">
            <span className="footer-note">
              <ShieldCheck size={14} strokeWidth={1.75} />
              Originais guardados criptografados neste servidor
            </span>
            <button className="button" type="submit" disabled={busy || (!front && !back)}>
              <ScanText size={16} strokeWidth={1.75} />
              Extrair dados
            </button>
          </div>
        </form>
        <ScanLinks />
      </div>
      {busy && (
        <div className="processing" role="status">
          <div className="processing-card">
            <span className="spinner" />
            <span>
              <strong>Lendo o documento</strong>
              <span>Corrigindo orientação, extraindo campos e validando o CPF.</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
