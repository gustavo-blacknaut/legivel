import { Trash2 } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { plural } from "../format";

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

type DeleteDialogProps = {
  open: boolean;
  title: string;
  description: ReactNode;
  documents: number;
  images: number;
  confirmationValues?: string[];
  confirmationLabel?: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
};

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[.\-\s]/g, "")
    .toUpperCase();
}

export function DeleteDialog({
  open,
  title,
  description,
  documents,
  images,
  confirmationValues = [],
  confirmationLabel,
  onConfirm,
  onClose,
}: DeleteDialogProps) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const inputId = useId();

  useEffect(() => {
    if (!open) return;
    setTyped("");
    setError(null);
    const previous = document.activeElement as HTMLElement | null;
    const first = dialogRef.current?.querySelector<HTMLElement>(confirmationValues.length ? "input" : "[data-cancel]");
    first?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open, confirmationValues.length]);

  if (!open) return null;

  const required = confirmationValues.filter(Boolean).map(normalize);
  const confirmed = required.length === 0 || required.includes(normalize(typed));

  const trapFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape" && !busy) {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const confirm = async () => {
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível apagar.");
      setBusy(false);
    }
  };

  return createPortal(
    <div className="dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <div
        ref={dialogRef}
        className="dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onKeyDown={trapFocus}
      >
        <span className="sheet-handle" aria-hidden="true" />
        <div className="dialog-body">
          <span className="dialog-icon" aria-hidden="true">
            <Trash2 size={20} strokeWidth={1.75} />
          </span>
          <h2 id={titleId}>{title}</h2>
          <p id={descriptionId}>{description}</p>
          <div className="impact" aria-label="O que será apagado">
            <div>
              <strong>{documents.toLocaleString("pt-BR")}</strong>
              <span>{documents === 1 ? "documento" : "documentos"}</span>
            </div>
            <div>
              <strong>{images.toLocaleString("pt-BR")}</strong>
              <span>{images === 1 ? "imagem e recorte" : "imagens e recortes"}</span>
            </div>
          </div>
          <p className="muted">
            Esta ação remove {plural(documents, "documento", "documentos")} e os arquivos criptografados do servidor. Não
            pode ser desfeita.
          </p>
          {required.length > 0 && (
            <div className="field">
              <label className="field-label" htmlFor={inputId}>
                {confirmationLabel}
              </label>
              <input
                id={inputId}
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && confirm()}
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
              />
            </div>
          )}
          {error && <p className="field-error">{error}</p>}
        </div>
        <div className="dialog-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={busy} data-cancel>
            Cancelar
          </button>
          <button className="button button-danger" type="button" onClick={confirm} disabled={!confirmed || busy}>
            <Trash2 size={16} strokeWidth={1.75} />
            {busy ? "Apagando…" : "Apagar definitivamente"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
