"use client";

import { Trash2 } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { normalizeForMatch } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import { Dialog, dialogStyles } from "./Dialog";

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

export function DeleteDialog(props: DeleteDialogProps) {
  return props.open ? <DeleteDialogBody {...props} /> : null;
}

function DeleteDialogBody({
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
  const { t, format } = useLocale();
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();

  const required = confirmationValues.filter(Boolean).map(normalizeForMatch);
  const confirmed = required.length === 0 || required.includes(normalizeForMatch(typed));

  const confirm = async () => {
    if (!confirmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.deleteDialog.failed);
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      title={title}
      role="alertdialog"
      busy={busy}
      icon={<Trash2 size={20} strokeWidth={1.75} />}
      initialFocus={required.length ? "input" : "[data-cancel]"}
      onClose={onClose}
      actions={
        <>
          <button className="button button-secondary" type="button" onClick={onClose} disabled={busy} data-cancel>
            {t.common.cancel}
          </button>
          <button className="button button-danger" type="button" onClick={confirm} disabled={!confirmed || busy}>
            <Trash2 size={16} strokeWidth={1.75} />
            {busy ? t.deleteDialog.deleting : t.deleteDialog.confirm}
          </button>
        </>
      }
    >
      <p>{description}</p>
      <div className={dialogStyles.impact} aria-label={t.deleteDialog.impact}>
        <div>
          <strong>{format.number(documents)}</strong>
          <span>{t.deleteDialog.documents(documents)}</span>
        </div>
        <div>
          <strong>{format.number(images)}</strong>
          <span>{t.deleteDialog.images(images)}</span>
        </div>
      </div>
      <p className="muted">{t.deleteDialog.irreversible(documents)}</p>
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
    </Dialog>
  );
}
