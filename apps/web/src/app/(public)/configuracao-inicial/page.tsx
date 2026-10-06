"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { useInstance } from "@/components/Providers";
import { api } from "@/lib/api/endpoints";
import { emailField, newPasswordSchema, requiredText, validate, type FieldErrors } from "@/lib/forms";
import { useT } from "@/lib/i18n";
import { ME_KEY } from "@/lib/session";
import { AuthCard, TextField, authStyles } from "../AuthCard";

export default function SetupPage() {
  const t = useT();
  const instance = useInstance();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [values, setValues] = useState({ name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setValues((current) => ({ ...current, [key]: event.target.value }));

  if (!instance.setup_required) {
    return (
      <AuthCard>
        <h1>{t.setup.title}</h1>
        <p>{t.setup.already}</p>
        <div className={authStyles.links}>
          <Link href="/entrar">{t.forgot.backToLogin}</Link>
        </div>
      </AuthCard>
    );
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const schema = newPasswordSchema(t, instance.password_min_length, instance.password_require_mixed).and(
      z.object({ name: requiredText(t), email: emailField(t) }),
    );
    const result = validate(schema, values);
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    setFailure(null);
    setBusy(true);
    try {
      await api.setup({ name: result.data.name, email: result.data.email, password: result.data.password });
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
      router.replace("/pessoas");
    } catch (caught) {
      setFailure(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
      router.refresh();
    }
  };

  return (
    <AuthCard>
      <form onSubmit={submit} noValidate className="stack">
        <h1>{t.setup.title}</h1>
        <p>{t.setup.intro}</p>
        {failure && (
          <div className="alert alert-danger" role="alert">
            {failure}
          </div>
        )}
        <TextField id="name" label={t.setup.name} value={values.name} onChange={set("name")} autoComplete="name" error={errors.name} />
        <TextField id="email" label={t.login.email} type="email" value={values.email} onChange={set("email")} autoComplete="email" error={errors.email} />
        <TextField id="password" label={t.password.new} type="password" value={values.password} onChange={set("password")} autoComplete="new-password" error={errors.password} />
        <TextField id="confirm" label={t.password.confirm} type="password" value={values.confirm} onChange={set("confirm")} autoComplete="new-password" error={errors.confirm} />
        <p className="field-hint">{t.password.rules(instance.password_min_length, instance.password_require_mixed)}</p>
        <button className="button button-lg button-block" type="submit" disabled={busy}>
          {t.setup.submit}
        </button>
      </form>
    </AuthCard>
  );
}
