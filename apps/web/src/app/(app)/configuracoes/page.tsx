"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ImageUp, RefreshCw, Save, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { Forbidden } from "@/components/Forbidden";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { FORMAT_LABELS } from "@/components/PhotoInput";
import { useToast } from "@/components/Toast";
import { api, type SettingsInfo } from "@/lib/api/endpoints";
import { useLocale } from "@/lib/i18n";
import type { Messages } from "@/lib/i18n/pt-BR";
import { useSession } from "@/lib/session";
import styles from "./settings.module.css";

type Value = string | number | boolean;
type FieldSpec =
  | { key: string; label: string; kind: "text"; max: number }
  | { key: string; label: string; kind: "number"; min: number; max: number; hint?: string }
  | { key: string; label: string; kind: "boolean" }
  | { key: string; label: string; kind: "select"; options: { value: string; label: string }[]; hint?: string }
  | { key: string; label: string; kind: "formats" }
  | { key: string; label: string; kind: "timezone"; zones: string[]; hint?: string };

const BRAZIL_ZONES = [
  "America/Sao_Paulo", "America/Bahia", "America/Fortaleza", "America/Recife", "America/Belem", "America/Manaus",
  "America/Cuiaba", "America/Campo_Grande", "America/Porto_Velho", "America/Boa_Vista", "America/Rio_Branco", "America/Noronha",
];
const ALL_FORMATS = ["jpeg", "png", "webp", "heic"];

function display(value: unknown, t: Messages): string {
  if (typeof value === "boolean") return value ? t.common.yes : t.common.no;
  return String(value ?? "");
}

type SectionProps = { title: string; fields: FieldSpec[]; info: SettingsInfo; hint?: ReactNode; action?: ReactNode; children?: ReactNode };

function SettingsSection({ title, fields, info, hint, action, children }: SectionProps) {
  const { t, setTimeZone } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();
  const initial = () => Object.fromEntries(fields.map((field) => [field.key, info.values[field.key] as Value]));
  const [draft, setDraft] = useState<Record<string, Value>>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const changed = fields.filter((field) => draft[field.key] !== info.values[field.key]);
  const set = (key: string, value: Value) => setDraft((current) => ({ ...current, [key]: value }));

  const persist = async (values: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const saved = await api.saveSettings(values);
      queryClient.setQueryData(["settings"], saved);
      if (typeof saved.values.timezone === "string") setTimeZone(saved.values.timezone);
      await queryClient.invalidateQueries({ queryKey: ["system"] });
      toast(t.settings.saved);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.common.error);
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void persist(Object.fromEntries(changed.map((field) => [field.key, draft[field.key]])));
  };

  return (
    <form className="panel" onSubmit={submit} noValidate>
      <div className="panel-head">
        <h2>{title}</h2>
        {action}
      </div>
      <div className="panel-body form-grid">
        {hint && <p className="muted flush span-2">{hint}</p>}
        {fields.map((field) => {
          const overridden = info.overridden.includes(field.key);
          const footer = (
            <span className="field-hint">
              {t.common.defaultValue(display(info.defaults[field.key], t))}
              {overridden && (
                <>
                  {" · "}
                  <button className={styles.inlineLink} type="button" onClick={() => persist({ [field.key]: null })}>
                    {t.common.useDefault}
                  </button>
                </>
              )}
            </span>
          );
          if (field.kind === "boolean") {
            return (
              <div key={field.key} className="field span-2">
                <label className="check">
                  <input type="checkbox" checked={Boolean(draft[field.key])} onChange={(event) => set(field.key, event.target.checked)} />
                  {field.label}
                </label>
                {footer}
              </div>
            );
          }
          if (field.kind === "formats") {
            const selected = String(draft[field.key] ?? "").split(",").filter(Boolean);
            const toggle = (format: string) => {
              const next = selected.includes(format) ? selected.filter((item) => item !== format) : [...selected, format];
              set(field.key, ALL_FORMATS.filter((item) => next.includes(item)).join(","));
            };
            return (
              <fieldset key={field.key} className={`field span-2 ${styles.fieldset}`}>
                <legend className="field-label">{field.label}</legend>
                <div className={styles.checks}>
                  {ALL_FORMATS.map((format) => (
                    <label key={format} className="check">
                      <input type="checkbox" checked={selected.includes(format)} onChange={() => toggle(format)} />
                      {FORMAT_LABELS[format]}
                    </label>
                  ))}
                </div>
                {footer}
              </fieldset>
            );
          }
          return (
            <label key={field.key} className={`field ${field.kind === "text" || field.kind === "timezone" ? "span-2" : ""}`}>
              <span className="field-label">{field.label}</span>
              {field.kind === "text" && (
                <input value={String(draft[field.key] ?? "")} maxLength={field.max} onChange={(event) => set(field.key, event.target.value)} />
              )}
              {field.kind === "number" && (
                <input
                  type="number"
                  inputMode="numeric"
                  min={field.min}
                  max={field.max}
                  value={String(draft[field.key] ?? "")}
                  onChange={(event) => set(field.key, event.target.value === "" ? "" : Number(event.target.value))}
                />
              )}
              {field.kind === "select" && (
                <select value={String(draft[field.key] ?? "")} onChange={(event) => set(field.key, event.target.value)}>
                  {field.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
              {field.kind === "timezone" && (
                <select value={String(draft[field.key] ?? "")} onChange={(event) => set(field.key, event.target.value)}>
                  <optgroup label={t.settings.brazil}>
                    {BRAZIL_ZONES.map((zone) => (
                      <option key={zone} value={zone}>
                        {zone.replace("America/", "").replace(/_/g, " ")}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label={t.settings.others}>
                    {field.zones
                      .filter((zone) => !BRAZIL_ZONES.includes(zone))
                      .map((zone) => (
                        <option key={zone} value={zone}>
                          {zone}
                        </option>
                      ))}
                  </optgroup>
                </select>
              )}
              {"hint" in field && field.hint && <span className="field-hint">{field.hint}</span>}
              {footer}
            </label>
          );
        })}
        {error && <p className="field-error span-2 flush">{error}</p>}
      </div>
      {children}
      <div className="panel-foot">
        <button className="button" type="submit" disabled={busy || changed.length === 0}>
          <Save size={16} strokeWidth={1.75} />
          {t.common.save}
        </button>
      </div>
    </form>
  );
}

function LogoSection({ info }: { info: SettingsInfo }) {
  const { t } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: ["settings"] });
    toast(t.settings.logoSaved);
    window.location.reload();
  };
  const upload = async (file: File | undefined) => {
    if (!file) return;
    try {
      await api.uploadLogo(file);
      await done();
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.settings.logo}</h2>
      </div>
      <div className="panel-body stack">
        <p className="muted flush">{t.settings.logoHint}</p>
        <div className="actions-row">
          <input ref={input} className={styles.hidden} type="file" accept="image/png,image/webp,image/jpeg" onChange={(event) => upload(event.target.files?.[0])} />
          <button className="button button-secondary" type="button" onClick={() => input.current?.click()}>
            <ImageUp size={16} strokeWidth={1.75} />
            {t.settings.logoUpload}
          </button>
          {info.has_logo && (
            <button className="button button-danger-ghost" type="button" onClick={() => api.removeLogo().then(done)}>
              <Trash2 size={16} strokeWidth={1.75} />
              {t.settings.logoRemove}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function RolesSection({ info }: { info: SettingsInfo }) {
  const { t } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();
  const editable = ["reviewer", "reader"] as const;
  const [draft, setDraft] = useState<Record<string, string[]>>(() => ({ reviewer: info.role_permissions.reviewer ?? [], reader: info.role_permissions.reader ?? [] }));
  const toggle = (role: string, permission: string) =>
    setDraft((current) => {
      const values = current[role] ?? [];
      return { ...current, [role]: values.includes(permission) ? values.filter((item) => item !== permission) : [...values, permission] };
    });
  const save = async () => {
    try {
      queryClient.setQueryData(["settings"], await api.saveRolePermissions(draft));
      toast(t.settings.rolesSaved);
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.settings.roles}</h2>
      </div>
      <div className="panel-body stack">
        <p className="muted flush">{t.settings.rolesHint}</p>
        <div className={styles.matrixWrap}>
          <table className={styles.matrix}>
            <thead>
              <tr>
                <th scope="col">{t.users.role}</th>
                {editable.map((role) => (
                  <th key={role} scope="col">
                    {t.roles[role]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {info.assignable_permissions.map((permission) => (
                <tr key={permission}>
                  <th scope="row">{t.settings.permissions[permission] ?? permission}</th>
                  {editable.map((role) => (
                    <td key={role}>
                      <input
                        type="checkbox"
                        aria-label={`${t.roles[role]}: ${t.settings.permissions[permission] ?? permission}`}
                        checked={(draft[role] ?? []).includes(permission)}
                        disabled={permission === "documents.view"}
                        onChange={() => toggle(role, permission)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="panel-foot">
        <button className="button" type="button" onClick={save}>
          <Save size={16} strokeWidth={1.75} />
          {t.common.save}
        </button>
      </div>
    </section>
  );
}

function useOcrStatus() {
  const { t } = useLocale();
  const system = useQuery({ queryKey: ["system"], queryFn: api.system });
  const status = system.data?.ocr_status ?? {};
  const rows = Object.entries(t.settings.ocrLabels)
    .map(([key, label]): [string, string] | null => {
      const value = status[key];
      if (key === "image_average_ms") {
        return [label, typeof value === "number" ? t.settings.milliseconds(value, Number(status.images ?? 0)) : t.settings.noReadings];
      }
      if (key === "average_ms") {
        return typeof value === "number" ? [label, t.settings.readings(value, Number(status.readings ?? 0))] : null;
      }
      return value === null || value === undefined || value === "" ? null : [label, String(value)];
    })
    .filter((row): row is [string, string] => row !== null);
  const containerized = status.adapters === "indisponível fora do Windows";
  const warning = typeof status.warning === "string" && status.warning ? status.warning : null;
  const refresh = (
    <button className="button button-ghost" type="button" onClick={() => system.refetch()}>
      <RefreshCw size={16} strokeWidth={1.75} className={system.isFetching ? "spin" : undefined} />
      {t.settings.refresh}
    </button>
  );
  const details = (
    <>
      {containerized && <div className={`alert alert-warning ${styles.warning}`}>{t.settings.dockerGpu}</div>}
      {warning && <div className={`alert alert-warning ${styles.warning}`}>{warning}</div>}
      <dl className={`meta-list panel-body ${styles.status}`}>
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt>{label}</dt>
            <dd className={label === t.settings.ocrLabels.providers || label === t.settings.ocrLabels.packages ? "mono" : undefined}>{value}</dd>
          </div>
        ))}
      </dl>
    </>
  );
  return { refresh, details };
}

function ServerSection() {
  const { t } = useLocale();
  const system = useQuery({ queryKey: ["system"], queryFn: api.system });
  const data = system.data;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.settings.server}</h2>
      </div>
      <div className="panel-body stack">
        <dl className="meta-list">
          <dt>{t.settings.database}</dt>
          <dd>{data?.database === "postgresql" ? "PostgreSQL" : data ? "SQLite" : "—"}</dd>
          <dt>{t.settings.email}</dt>
          <dd>{data ? (data.smtp_configured ? t.settings.configured : t.settings.notConfigured) : "—"}</dd>
          <dt>{t.settings.encryption}</dt>
          <dd>{data ? (data.encrypted_storage ? t.settings.encrypted : t.settings.notEncrypted) : "—"}</dd>
          <dt>{t.settings.languages}</dt>
          <dd className="mono">{data?.ocr_languages ?? "—"}</dd>
        </dl>
        <p className="muted flush">{t.settings.envOnly}</p>
      </div>
    </section>
  );
}

export default function SettingsPage() {
  const { t } = useLocale();
  const { can } = useSession();
  const allowed = can("settings.manage");
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings, enabled: allowed });
  const zones = useQuery({ queryKey: ["timezones"], queryFn: api.timezones, enabled: allowed, staleTime: Infinity });
  const ocrStatus = useOcrStatus();
  if (!allowed) return <Forbidden />;
  const info = settings.data;
  if (!info) return <div className="spinner spinner-page" role="status" />;

  const themeOptions = (["system", "light", "dark"] as const).map((value) => ({ value, label: t.account.themes[value] }));
  const languageOptions = (["pt-BR", "en"] as const).map((value) => ({ value, label: t.account.languages[value] }));
  const deviceOptions = (["auto", "cpu", "gpu"] as const).map((value) => ({ value, label: t.settings.devices[value] }));

  return (
    <div className={page.page}>
      <PageHead title={t.settings.title} description={t.settings.description} />
      <div className={page.settings}>
        <SettingsSection
          key={`instance-${settings.dataUpdatedAt}`}
          title={t.settings.instance}
          info={info}
          fields={[
            { key: "instance_name", label: t.settings.instanceName, kind: "text", max: 60 },
            { key: "default_theme", label: t.settings.defaultTheme, kind: "select", options: themeOptions },
            { key: "default_language", label: t.settings.defaultLanguage, kind: "select", options: languageOptions },
            { key: "timezone", label: t.settings.timezone, kind: "timezone", zones: zones.data ?? [], hint: t.settings.timezoneHint },
          ]}
        />
        <LogoSection info={info} />
        <SettingsSection
          key={`ocr-${settings.dataUpdatedAt}`}
          title={t.settings.ocr}
          info={info}
          action={ocrStatus.refresh}
          fields={[
            { key: "ocr_device", label: t.settings.ocrDevice, kind: "select", options: deviceOptions, hint: t.settings.ocrDeviceHint },
            { key: "ocr_passes", label: t.settings.ocrPasses, kind: "number", min: 1, max: 4, hint: t.settings.ocrPassesHint },
          ]}
        >
          {ocrStatus.details}
        </SettingsSection>
        <SettingsSection
          key={`uploads-${settings.dataUpdatedAt}`}
          title={t.settings.uploads}
          info={info}
          fields={[
            { key: "upload_max_mb", label: t.settings.uploadMax, kind: "number", min: 1, max: 100 },
            { key: "image_quality", label: t.settings.imageQuality, kind: "number", min: 40, max: 100 },
            { key: "upload_formats", label: t.settings.uploadFormats, kind: "formats" },
            { key: "compress_originals", label: t.settings.compressOriginals, kind: "boolean" },
          ]}
        />
        <SettingsSection
          key={`retention-${settings.dataUpdatedAt}`}
          title={t.settings.retention}
          info={info}
          hint={t.settings.retentionHint}
          fields={[{ key: "retention_days", label: t.settings.retentionDays, kind: "number", min: 0, max: 36500 }]}
        />
        <SettingsSection
          key={`security-${settings.dataUpdatedAt}`}
          title={t.settings.security}
          info={info}
          fields={[
            { key: "password_min_length", label: t.settings.passwordMin, kind: "number", min: 8, max: 128 },
            { key: "login_max_attempts", label: t.settings.loginAttempts, kind: "number", min: 1, max: 100 },
            { key: "login_lock_minutes", label: t.settings.lockMinutes, kind: "number", min: 1, max: 1440 },
            { key: "refresh_days", label: t.settings.refreshDays, kind: "number", min: 1, max: 365 },
            { key: "session_idle_hours", label: t.settings.idleHours, kind: "number", min: 1, max: 720 },
            { key: "invite_hours", label: t.settings.inviteHours, kind: "number", min: 1, max: 720 },
            { key: "scan_link_hours", label: t.settings.scanLinkHours, kind: "number", min: 1, max: 720 },
            { key: "password_require_mixed", label: t.settings.passwordMixed, kind: "boolean" },
          ]}
        />
        <RolesSection info={info} />
        <ServerSection />
      </div>
    </div>
  );
}
