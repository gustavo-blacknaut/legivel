"use client";

import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useInstance } from "@/components/Providers";
import { api } from "@/lib/api/endpoints";
import { newPasswordSchema, validate, type FieldErrors } from "@/lib/forms";
import { useT } from "@/lib/i18n";
import { AuthCard, TextField, authStyles } from "../../AuthCard";

export default function ResetPasswordPage() {
  const t = useT();
  const instance = useInstance();
  const token = useParams<{ token: string }>().token;
  const [values, setValues] = useState({ password: "", confirm: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(newPasswordSchema(t, instance.password_min_length, instance.password_require_mixed), values);
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    setFailure(null);
    setBusy(true);
    try {
      await api.resetPassword(token, result.data.password);
      setDone(true);
    } catch (caught) {
      setFailure(caught instanceof Error ? caught.message : t.common.error);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthCard>
        <div className={authStyles.message}>
          <CircleCheck size={32} strokeWidth={1.5} className={authStyles.success} />
          <h1>{t.reset.doneTitle}</h1>
          <p>{t.reset.doneText}</p>
          <Link href="/entrar" className="button">
            {t.reset.goToLogin}
          </Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard>
      <form onSubmit={submit} noValidate className="stack">
        <h1>{t.reset.title}</h1>
        {failure && (
          <div className="alert alert-danger" role="alert">
            {failure}
          </div>
        )}
        <TextField
          id="password"
          label={t.password.new}
          type="password"
          value={values.password}
          onChange={(event) => setValues((current) => ({ ...current, password: event.target.value }))}
          autoComplete="new-password"
          error={errors.password}
        />
        <TextField
          id="confirm"
          label={t.password.confirm}
          type="password"
          value={values.confirm}
          onChange={(event) => setValues((current) => ({ ...current, confirm: event.target.value }))}
          autoComplete="new-password"
          error={errors.confirm}
        />
        <p className="field-hint">{t.password.rules(instance.password_min_length, instance.password_require_mixed)}</p>
        <button className="button button-lg button-block" type="submit" disabled={busy}>
          {t.reset.submit}
        </button>
        <div className={authStyles.links}>
          <Link href="/entrar">{t.forgot.backToLogin}</Link>
        </div>
      </form>
    </AuthCard>
  );
}
