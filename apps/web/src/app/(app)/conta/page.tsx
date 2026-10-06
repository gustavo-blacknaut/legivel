"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, LaptopMinimal, LogOut, Monitor, Moon, ShieldCheck, Sun, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { useInstance } from "@/components/Providers";
import { useTheme } from "@/components/ThemeProvider";
import { useToast } from "@/components/Toast";
import { api, type TwoFactorSetup } from "@/lib/api/endpoints";
import { describeDevice, type Language } from "@/lib/format";
import { codeField, emailField, newPasswordSchema, requiredText, validate, type FieldErrors } from "@/lib/forms";
import { useLocale } from "@/lib/i18n";
import { ME_KEY, useSession } from "@/lib/session";
import type { ThemePreference } from "@/lib/theme";
import styles from "./account.module.css";

function FieldError({ errors, name }: { errors: FieldErrors; name: string }) {
  return errors[name] ? <span className="field-error">{errors[name]}</span> : null;
}

function ProfileSection() {
  const { t } = useLocale();
  const { user } = useSession();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState(user.name);
  const [errors, setErrors] = useState<FieldErrors>({});
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ name: requiredText(t) }), { name });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    try {
      queryClient.setQueryData(ME_KEY, await api.updateProfile(result.data.name));
      toast(t.account.profileSaved);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.account.profile}</h2>
      </div>
      <form className="panel-body actions-row" onSubmit={submit} noValidate>
        <label className={`field grow ${errors.name ? "field-invalid" : ""}`}>
          <span className="field-label">{t.account.name}</span>
          <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" maxLength={120} />
          <FieldError errors={errors} name="name" />
        </label>
        <button className="button" type="submit" disabled={name.trim() === user.name}>
          {t.common.save}
        </button>
      </form>
    </section>
  );
}

function EmailSection() {
  const { t } = useLocale();
  const { user } = useSession();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ email: emailField(t), password: z.string().min(1, t.validation.required) }), { email, password });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    try {
      const delivery = await api.changeEmail(result.data);
      toast(delivery.detail, delivery.emailed ? "ok" : "error");
      setEmail("");
      setPassword("");
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.account.emailTitle}</h2>
      </div>
      <div className="panel-body stack">
        <dl className="meta-list">
          <dt>{t.account.currentEmail}</dt>
          <dd>{user.email}</dd>
        </dl>
        <form className="form-grid" onSubmit={submit} noValidate>
          <label className={`field ${errors.email ? "field-invalid" : ""}`}>
            <span className="field-label">{t.account.newEmail}</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" />
            <FieldError errors={errors} name="email" />
          </label>
          <label className={`field ${errors.password ? "field-invalid" : ""}`}>
            <span className="field-label">{t.account.confirmPassword}</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
            <FieldError errors={errors} name="password" />
          </label>
          <div className="span-2">
            <button className="button button-secondary" type="submit">
              {t.account.requestChange}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function PasswordSection() {
  const { t } = useLocale();
  const instance = useInstance();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const queryClient = useQueryClient();
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const schema = newPasswordSchema(t, instance.password_min_length, instance.password_require_mixed).and(
      z.object({ current: z.string().min(1, t.validation.required) }),
    );
    const result = validate(schema, { current, password, confirm });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    try {
      const response = (await api.changePassword({ current_password: current, new_password: password })) as { revoked_sessions?: number };
      toast(t.account.passwordChanged(response.revoked_sessions ?? 0));
      setCurrent("");
      setPassword("");
      setConfirm("");
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.account.passwordTitle}</h2>
      </div>
      <form className="panel-body form-grid" onSubmit={submit} noValidate>
        <label className={`field span-2 ${errors.current ? "field-invalid" : ""}`}>
          <span className="field-label">{t.password.current}</span>
          <input type="password" value={current} onChange={(event) => setCurrent(event.target.value)} autoComplete="current-password" />
          <FieldError errors={errors} name="current" />
        </label>
        <label className={`field ${errors.password ? "field-invalid" : ""}`}>
          <span className="field-label">{t.password.new}</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" />
          <FieldError errors={errors} name="password" />
        </label>
        <label className={`field ${errors.confirm ? "field-invalid" : ""}`}>
          <span className="field-label">{t.password.confirm}</span>
          <input type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} autoComplete="new-password" />
          <FieldError errors={errors} name="confirm" />
        </label>
        <p className="field-hint span-2 flush">{t.password.rules(instance.password_min_length, instance.password_require_mixed)}</p>
        <div className="span-2">
          <button className="button" type="submit">
            <KeyRound size={16} strokeWidth={1.75} />
            {t.account.changePassword}
          </button>
        </div>
      </form>
    </section>
  );
}

function TwoFactorSection() {
  const { t } = useLocale();
  const { user } = useSession();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [setup, setSetup] = useState<TwoFactorSetup | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const refresh = () => queryClient.invalidateQueries({ queryKey: ME_KEY });

  const start = async () => {
    try {
      setSetup(await api.startTwoFactor());
      setCode("");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  const confirm = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ code: codeField(t) }), { code });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    try {
      const response = await api.confirmTwoFactor(result.data.code.replace(/\s/g, ""));
      setCodes(response.recovery_codes);
      setSetup(null);
      await refresh();
    } catch (caught) {
      setErrors({ code: caught instanceof Error ? caught.message : t.common.error });
    }
  };
  const disable = async (event: FormEvent) => {
    event.preventDefault();
    if (!password) return setErrors({ password: t.validation.required });
    setErrors({});
    try {
      await api.disableTwoFactor(password);
      setPassword("");
      toast(t.account.twoFactorDisabled);
      await refresh();
    } catch (caught) {
      setErrors({ password: caught instanceof Error ? caught.message : t.common.error });
    }
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.account.twoFactor}</h2>
        {user.two_factor_enabled && (
          <span className="status status-reviewed">
            <span className="status-dot" aria-hidden="true" />
            {t.users.active}
          </span>
        )}
      </div>
      <div className="panel-body stack">
        <p className="muted flush">{user.two_factor_enabled ? t.account.twoFactorOn : t.account.twoFactorOff}</p>
        {codes && (
          <div className={styles.codes}>
            <strong>{t.account.recoveryTitle}</strong>
            <p className="muted flush">{t.account.recoveryText}</p>
            <ul className="mono">
              {codes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <button className="button button-secondary" type="button" onClick={() => setCodes(null)}>
              {t.account.recoveryDone}
            </button>
          </div>
        )}
        {!user.two_factor_enabled && !setup && !codes && (
          <div>
            <button className="button" type="button" onClick={start}>
              <ShieldCheck size={16} strokeWidth={1.75} />
              {t.account.twoFactorStart}
            </button>
          </div>
        )}
        {setup && (
          <form className={styles.setup} onSubmit={confirm} noValidate>
            <img className={styles.qr} src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`} alt="QR code" width={200} height={200} />
            <div className="stack">
              <p className="flush">{t.account.twoFactorScan}</p>
              <label className="field">
                <span className="field-label">{t.account.twoFactorSecret}</span>
                <input readOnly value={setup.secret} className="mono" onFocus={(event) => event.target.select()} />
              </label>
              <label className={`field ${errors.code ? "field-invalid" : ""}`}>
                <span className="field-label">{t.login.code}</span>
                <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={16} />
                <FieldError errors={errors} name="code" />
              </label>
              <div className="actions-row">
                <button className="button" type="submit">
                  {t.account.twoFactorConfirm}
                </button>
                <button className="button button-ghost" type="button" onClick={() => setSetup(null)}>
                  {t.common.cancel}
                </button>
              </div>
            </div>
          </form>
        )}
        {user.two_factor_enabled && !codes && (
          <form className="actions-row" onSubmit={disable} noValidate>
            <label className={`field grow ${errors.password ? "field-invalid" : ""}`}>
              <span className="field-label">{t.account.confirmPassword}</span>
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
              <FieldError errors={errors} name="password" />
            </label>
            <button className="button button-danger-ghost" type="submit">
              {t.account.twoFactorDisable}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}

function SessionsSection() {
  const { t, format } = useLocale();
  const instance = useInstance();
  const toast = useToast();
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  const items = sessions.data ?? [];
  const reload = () => queryClient.invalidateQueries({ queryKey: ["sessions"] });
  const revokeOthers = async () => {
    const result = await api.revokeOtherSessions();
    toast(t.account.revoked(result.revoked ?? 0));
    await reload();
  };
  const end = async (id: number) => {
    await api.endSession(id);
    toast(t.account.sessionEnded);
    await reload();
  };
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.account.sessions}</h2>
        <button className="button button-secondary" type="button" onClick={revokeOthers} disabled={items.length < 2}>
          {t.account.revokeOthers}
        </button>
      </div>
      <ul className={styles.sessions}>
        {items.map((item) => (
          <li key={item.id}>
            <LaptopMinimal size={18} strokeWidth={1.5} />
            <span className={styles.sessionMain}>
              <strong>
                {describeDevice(item.user_agent, t.common.unknownDevice)}
                {item.current && <span className="tag">{t.account.thisDevice}</span>}
              </strong>
              <span className="muted">
                {t.account.sessionLine(item.ip_address ?? t.account.unknownIp, format.dateTime(item.created_at), format.dateTime(item.expires_at))}
              </span>
            </span>
            {!item.current && (
              <button className="icon-button" type="button" aria-label={t.account.endSession} title={t.account.endSession} onClick={() => end(item.id)}>
                <X size={16} />
              </button>
            )}
          </li>
        ))}
      </ul>
      <div className="panel-body">
        <p className="muted flush">{t.account.sessionNote(instance.refresh_days)}</p>
      </div>
    </section>
  );
}

function AppearanceSection() {
  const { t, language, setLanguage } = useLocale();
  const { preference, setPreference } = useTheme();
  const themes: { value: ThemePreference; icon: typeof Sun }[] = [
    { value: "light", icon: Sun },
    { value: "dark", icon: Moon },
    { value: "system", icon: Monitor },
  ];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.account.appearance}</h2>
      </div>
      <div className="panel-body stack">
        <div className="field">
          <span className="field-label">{t.account.theme}</span>
          <div className="segmented" role="group" aria-label={t.account.theme}>
            {themes.map(({ value, icon: Icon }) => (
              <button key={value} type="button" aria-pressed={preference === value} onClick={() => setPreference(value)}>
                <Icon size={14} strokeWidth={1.75} />
                {t.account.themes[value]}
              </button>
            ))}
          </div>
        </div>
        <label className="field">
          <span className="field-label">{t.account.language}</span>
          <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
            {(Object.keys(t.account.languages) as Language[]).map((value) => (
              <option key={value} value={value}>
                {t.account.languages[value]}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}

export default function AccountPage() {
  const { t } = useLocale();
  const { user, logout } = useSession();
  return (
    <div className={page.page}>
      <PageHead title={t.account.title} description={t.account.description(user.email)} />
      <div className={page.settings}>
        <ProfileSection />
        <AppearanceSection />
        <PasswordSection />
        <TwoFactorSection />
        <EmailSection />
        <SessionsSection />
        <button className={`button button-danger-ghost ${styles.logout}`} type="button" onClick={logout}>
          <LogOut size={16} strokeWidth={1.75} />
          {t.account.logout}
        </button>
      </div>
    </div>
  );
}
