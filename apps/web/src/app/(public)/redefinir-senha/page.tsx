"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { useInstance } from "@/components/Providers";
import { api } from "@/lib/api/endpoints";
import { emailField, validate, type FieldErrors } from "@/lib/forms";
import { useT } from "@/lib/i18n";
import { AuthCard, TextField, authStyles } from "../AuthCard";

export default function ForgotPasswordPage() {
  const t = useT();
  const instance = useInstance();
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [sent, setSent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ email: emailField(t) }), { email });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    setBusy(true);
    try {
      const response = (await api.forgotPassword(result.data.email)) as { detail?: string };
      setSent(response.detail ?? "");
    } catch (caught) {
      setErrors({ email: caught instanceof Error ? caught.message : t.common.error });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard>
      <form onSubmit={submit} noValidate className="stack">
        <h1>{t.forgot.title}</h1>
        {!instance.smtp_configured && <div className="alert alert-warning">{t.forgot.noSmtp}</div>}
        {sent !== null ? (
          <div className="alert alert-ok" role="status">
            {sent}
          </div>
        ) : (
          <>
            <p>{t.forgot.intro}</p>
            <TextField id="email" label={t.login.email} type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" error={errors.email} />
            <button className="button button-lg button-block" type="submit" disabled={busy}>
              {t.forgot.submit}
            </button>
          </>
        )}
        <div className={authStyles.links}>
          <Link href="/entrar">{t.forgot.backToLogin}</Link>
        </div>
      </form>
    </AuthCard>
  );
}
