"use client";

import { Lock } from "lucide-react";
import type { ReactNode } from "react";
import { Brand } from "@/components/Brand";
import { useT } from "@/lib/i18n";
import styles from "./auth.module.css";

export function AuthCard({ children, note = true }: { children: ReactNode; note?: boolean }) {
  const t = useT();
  return (
    <main className={styles.screen}>
      <div className={styles.box}>
        <Brand className={styles.brand} size={32} />
        <div className={styles.card}>{children}</div>
        {note && (
          <p className={styles.note}>
            <Lock size={12} />
            {t.login.note}
          </p>
        )}
      </div>
    </main>
  );
}

export function TextField({
  id,
  label,
  error,
  ...input
}: { id: string; label: string; error?: string | undefined } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={`field ${error ? "field-invalid" : ""}`}>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input id={id} aria-invalid={Boolean(error) || undefined} aria-describedby={error ? `${id}-error` : undefined} {...input} />
      {error && (
        <span id={`${id}-error`} className="field-error">
          {error}
        </span>
      )}
    </div>
  );
}

export { styles as authStyles };
