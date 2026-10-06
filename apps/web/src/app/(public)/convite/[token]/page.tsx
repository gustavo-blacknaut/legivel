"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { useInstance } from "@/components/Providers";
import { api } from "@/lib/api/endpoints";
import { newPasswordSchema, requiredText, validate, type FieldErrors } from "@/lib/forms";
import { useT } from "@/lib/i18n";
import { AuthCard, TextField, authStyles } from "../../AuthCard";

export default function InvitationPage() {
  const t = useT();
  const instance = useInstance();
  const token = useParams<{ token: string }>().token;
  const router = useRouter();
  const preview = useQuery({ queryKey: ["invitation", token], queryFn: () => api.invitation(token), retry: false });
  const [values, setValues] = useState({ name: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setValues((current) => ({ ...current, [key]: event.target.value }));

  if (preview.isPending) {
    return (
      <AuthCard note={false}>
        <div className="spinner" role="status" />
      </AuthCard>
    );
  }
  if (preview.error || !preview.data) {
    return (
      <AuthCard note={false}>
        <div className={authStyles.message}>
          <CircleAlert size={32} strokeWidth={1.5} className={authStyles.failure} />
          <h1>{t.invite.invalidTitle}</h1>
          <p>{t.invite.invalidText}</p>
        </div>
      </AuthCard>
    );
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const schema = newPasswordSchema(t, instance.password_min_length, instance.password_require_mixed).and(z.object({ name: requiredText(t) }));
    const result = validate(schema, values);
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    setFailure(null);
    setBusy(true);
    try {
      await api.acceptInvitation(token, { name: result.data.name, password: result.data.password });
      router.replace("/pessoas");
    } catch (caught) {
      setFailure(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
    }
  };

  return (
    <AuthCard>
      <form onSubmit={submit} noValidate className="stack">
        <h1>{t.invite.title}</h1>
        <p>{t.invite.intro(preview.data.email, t.roles[preview.data.role].toLowerCase())}</p>
        {failure && (
          <div className="alert alert-danger" role="alert">
            {failure}
          </div>
        )}
        <TextField id="name" label={t.invite.name} value={values.name} onChange={set("name")} autoComplete="name" error={errors.name} />
        <TextField id="password" label={t.password.new} type="password" value={values.password} onChange={set("password")} autoComplete="new-password" error={errors.password} />
        <TextField id="confirm" label={t.password.confirm} type="password" value={values.confirm} onChange={set("confirm")} autoComplete="new-password" error={errors.confirm} />
        <p className="field-hint">{t.password.rules(instance.password_min_length, instance.password_require_mixed)}</p>
        <button className="button button-lg button-block" type="submit" disabled={busy}>
          {t.invite.submit}
        </button>
      </form>
    </AuthCard>
  );
}
