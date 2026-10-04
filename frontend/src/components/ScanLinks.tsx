import { Check, Copy, Link2, Send, Share2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { formatDateTime } from "../format";
import type { LinkState, ScanLink, ScanLinkCreated } from "../types";
import { useToast } from "./Toast";

const STATE_LABELS: Record<LinkState, string> = {
  active: "Aguardando envio",
  used: "Recebido",
  expired: "Expirado",
  revoked: "Cancelado",
};
const VALIDITY_OPTIONS = [
  { hours: 24, label: "24 horas" },
  { hours: 48, label: "2 dias" },
  { hours: 168, label: "7 dias" },
];
const REFRESH_INTERVAL_MS = 8000;

function linkUrl(token: string): string {
  return `${window.location.origin}/enviar/${token}`;
}

export function ScanLinks() {
  const toast = useToast();
  const [links, setLinks] = useState<ScanLink[]>([]);
  const [creating, setCreating] = useState(false);
  const [label, setLabel] = useState("");
  const [hours, setHours] = useState(48);
  const [created, setCreated] = useState<ScanLinkCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => api.scanLinks().then(setLinks).catch(() => undefined);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => document.visibilityState === "visible" && load(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const result = await api.createScanLink(label, hours);
      setCreated(result);
      setCopied(false);
      setLabel("");
      setCreating(false);
      load();
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : "Não foi possível gerar o link.", "error");
    }
  };

  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      toast("Copie o link manualmente.", "error");
    }
  };

  const share = async (url: string) => {
    try {
      await navigator.share({ title: "Envio de documento", text: "Envie a frente e o verso do seu documento por este link:", url });
    } catch {
      return;
    }
  };

  const revoke = async (link: ScanLink) => {
    await api.revokeScanLink(link.id);
    toast("Link cancelado.");
    load();
  };

  return (
    <section className="panel narrow">
      <div className="panel-head">
        <h2>Envio remoto</h2>
        {!creating && (
          <button className="button button-secondary" type="button" onClick={() => setCreating(true)}>
            <Link2 size={16} strokeWidth={1.75} />
            Gerar link de envio
          </button>
        )}
      </div>
      <div className="panel-body stack">
        <p className="muted flush">
          Gere um link e mande para a pessoa. Ela abre no celular, envia a frente e o verso, e o documento aparece aqui para revisão. Cada link aceita um único envio.
        </p>
        {creating && (
          <form className="actions-row" onSubmit={create}>
            <label className="field grow">
              <span className="field-label">Identificação (opcional)</span>
              <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Ex.: Admissão — vaga de recepção" maxLength={120} />
            </label>
            <label className="field">
              <span className="field-label">Validade</span>
              <select value={hours} onChange={(event) => setHours(Number(event.target.value))}>
                {VALIDITY_OPTIONS.map((option) => (
                  <option key={option.hours} value={option.hours}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button className="button" type="submit">
              <Send size={16} strokeWidth={1.75} />
              Gerar
            </button>
            <button className="button button-ghost" type="button" onClick={() => setCreating(false)}>
              Cancelar
            </button>
          </form>
        )}
        {created && (
          <div className="link-result">
            <span className="field-label">Link gerado{created.label ? ` para ${created.label}` : ""} — válido até {formatDateTime(created.expires_at)}</span>
            <div className="link-box">
              <input readOnly value={linkUrl(created.token)} onFocus={(event) => event.target.select()} aria-label="Link de envio" className="mono" />
              <button className="button" type="button" onClick={() => copy(linkUrl(created.token))}>
                {copied ? <Check size={16} /> : <Copy size={16} strokeWidth={1.75} />}
                {copied ? "Copiado" : "Copiar"}
              </button>
              {"share" in navigator && (
                <button className="button button-secondary" type="button" onClick={() => share(linkUrl(created.token))}>
                  <Share2 size={16} strokeWidth={1.75} />
                  Compartilhar
                </button>
              )}
            </div>
            <span className="field-hint">Por segurança o link completo só aparece agora. Se perder, gere outro.</span>
          </div>
        )}
      </div>
      {links.length > 0 && (
        <ul className="link-list">
          {links.map((link) => (
            <li key={link.id}>
              <span className={`status ${link.state === "used" ? "status-reviewed" : link.state === "active" ? "status-pending" : ""}`}>
                <span className="status-dot" aria-hidden="true" />
                {STATE_LABELS[link.state]}
              </span>
              <span className="link-label">{link.label || `Link #${link.id}`}</span>
              <span className="muted link-date">
                {link.used_at ? `recebido em ${formatDateTime(link.used_at)}` : `até ${formatDateTime(link.expires_at)}`}
              </span>
              {link.document_id ? (
                <Link to={`/documentos/${link.document_id}`} className="button button-ghost">
                  Abrir documento
                </Link>
              ) : link.state === "active" ? (
                <button className="icon-button" type="button" aria-label="Cancelar link" title="Cancelar link" onClick={() => revoke(link)}>
                  <X size={16} />
                </button>
              ) : (
                <span />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
