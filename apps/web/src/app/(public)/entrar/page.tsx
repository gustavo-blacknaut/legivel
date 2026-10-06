"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { z } from "zod";
import { useInstance } from "@/components/Providers";
import { api } from "@/lib/api/endpoints";
import { codeField, emailField, validate, type FieldErrors } from "@/lib/forms";
import { useT } from "@/lib/i18n";
import { safeReturnPath } from "@/lib/redirect";
import { ME_KEY } from "@/lib/session";
import { AuthCard, TextField, authStyles } from "../AuthCard";

function LoginForm() {
  const t = useT();
  const instance = useInstance();
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<"password" | "code">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const target = safeReturnPath(params.get("next"));

  useEffect(() => {
    if (instance.setup_required) router.replace("/configuracao-inicial");
  }, [instance.setup_required, router]);

  const finish = async () => {
    await queryClient.invalidateQueries({ queryKey: ME_KEY });
    router.replace(target);
  };

  const submitPassword = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ email: emailField(t), password: z.string().min(1, t.validation.required) }), { email, password });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    setFailure(null);
    setBusy(true);
    try {
      const response = await api.login(result.data);
      if (response.status === "two_factor") {
        setStage("code");
        setBusy(false);
        return;
      }
      await finish();
    } catch (caught) {
      setFailure(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
    }
  };

  const submitCode = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ code: codeField(t) }), { code });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    setFailure(null);
    setBusy(true);
    try {
      await api.loginTwoFactor(result.data.code.replace(/\s/g, ""));
      await finish();
    } catch (caught) {
      setFailure(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
      if (caught instanceof Error && "status" in caught && (caught as { status: number }).status === 401) {
        setStage("password");
        setCode("");
      }
    }
  };

  if (stage === "code") {
    return (
      <form onSubmit={submitCode} noValidate className="stack">
        <h1>{t.login.twoFactorTitle}</h1>
        <p>{t.login.twoFactorHint}</p>
        {failure && (
          <div className="alert alert-danger" role="alert">
            {failure}
          </div>
        )}
        <TextField
          id="code"
          label={t.login.code}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          maxLength={16}
          error={errors.code}
        />
        <button className="button button-lg button-block" type="submit" disabled={busy}>
          {t.login.verify}
        </button>
        <div className={authStyles.links}>
          <Link
            href="/entrar"
            onClick={(event) => {
              event.preventDefault();
              setStage("password");
            }}
          >
            {t.login.back}
          </Link>
        </div>
      </form>
    );
  }

  return (
    <form onSubmit={submitPassword} noValidate className="stack">
      <h1>{t.login.title}</h1>
      {params.get("next") && !failure && <p>{t.login.sessionExpired}</p>}
      {failure && (
        <div className="alert alert-danger" role="alert">
          {failure}
        </div>
      )}
      <TextField
        id="email"
        label={t.login.email}
        type="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        autoComplete="username"
        autoCapitalize="none"
        autoFocus
        error={errors.email}
      />
      <TextField
        id="password"
        label={t.login.password}
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        autoComplete="current-password"
        error={errors.password}
      />
      <button className="button button-lg button-block" type="submit" disabled={busy}>
        {busy ? t.login.submitting : t.login.submit}
      </button>
      <div className={authStyles.links}>
        <Link href="/redefinir-senha">{t.login.forgot}</Link>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthCard>
      <Suspense fallback={<div className="spinner" />}>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
