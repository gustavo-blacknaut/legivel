import { Check, CircleAlert, CircleCheck, Lock, ScanText } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { Brand } from "../components/AppShell";
import { Dropzone } from "../components/Dropzone";
import type { PublicLink } from "../types";

type Stage = "loading" | "ready" | "sending" | "done" | "unavailable";

export function PublicScanPage() {
  const token = useParams().token ?? "";
  const [link, setLink] = useState<PublicLink | null>(null);
  const [stage, setStage] = useState<Stage>("loading");
  const [front, setFront] = useState<File | null>(null);
  const [back, setBack] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .publicLink(token)
      .then((result) => {
        setLink(result);
        setStage(result.state === "active" ? "ready" : "unavailable");
      })
      .catch(() => setStage("unavailable"));
  }, [token]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const form = new FormData();
    if (front) form.append("front", front);
    if (back) form.append("back", back);
    setStage("sending");
    setError(null);
    try {
      await api.publicUpload(token, form);
      setStage("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível enviar.");
      setStage("ready");
    }
  };

  return (
    <main className="public-page">
      <header className="public-header">
        <Brand />
      </header>
      <div className="public-content">
        {stage === "loading" && <div className="spinner spinner-page" />}
        {stage === "unavailable" && (
          <div className="public-message">
            <CircleAlert size={32} strokeWidth={1.5} />
            <h1>Link indisponível</h1>
            <p>Este link já foi usado, expirou ou foi cancelado. Peça um novo link a quem solicitou o documento.</p>
          </div>
        )}
        {stage === "done" && (
          <div className="public-message success">
            <CircleCheck size={32} strokeWidth={1.5} />
            <h1>Documento enviado</h1>
            <p>Recebemos as fotos. Você já pode fechar esta página.</p>
          </div>
        )}
        {(stage === "ready" || stage === "sending") && (
          <form className="panel" onSubmit={submit}>
            <div className="panel-body stack">
              <div>
                <h1 className="public-title">Envio de documento</h1>
                <p className="muted flush">
                  {link?.label ? `${link.label}. ` : ""}Fotografe a frente e o verso do seu RG, CNH ou cartão CPF.
                </p>
              </div>
              {error && <div className="alert alert-danger">{error}</div>}
              <div className="upload">
                <Dropzone label="Frente" hint="Tirar foto ou escolher arquivo" file={front} onChange={setFront} />
                <Dropzone label="Verso" hint="Tirar foto ou escolher arquivo" file={back} onChange={setBack} />
              </div>
              <ul className="checklist">
                <li><Check size={16} strokeWidth={2} />Documento inteiro na foto, sem cortar as bordas</li>
                <li><Check size={16} strokeWidth={2} />Sem reflexo ou sombra sobre o texto</li>
              </ul>
            </div>
            <div className="form-footer">
              <span className="footer-note">
                <Lock size={14} strokeWidth={1.75} />
                Envio criptografado e de uso único
              </span>
              <button className="button button-lg" type="submit" disabled={stage === "sending" || (!front && !back)}>
                <ScanText size={18} strokeWidth={1.75} />
                {stage === "sending" ? "Enviando…" : "Enviar documento"}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
