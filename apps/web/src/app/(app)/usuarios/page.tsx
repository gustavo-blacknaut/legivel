"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Send, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { Forbidden } from "@/components/Forbidden";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { useToast } from "@/components/Toast";
import { api, type Account, type Role } from "@/lib/api/endpoints";
import { emailField, validate, type FieldErrors } from "@/lib/forms";
import { useLocale } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import styles from "./users.module.css";

const ROLES: Role[] = ["admin", "reviewer", "reader"];

function CopyLink({ link, note }: { link: string; note: string }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className={styles.result}>
      <span className="field-label">{note}</span>
      <div className={styles.linkBox}>
        <input readOnly value={link} className="mono" onFocus={(event) => event.target.select()} aria-label={note} />
        <button className="button" type="button" onClick={copy}>
          {copied ? <Check size={16} /> : <Copy size={16} strokeWidth={1.75} />}
          {copied ? t.common.copied : t.common.copy}
        </button>
      </div>
    </div>
  );
}

function InviteSection() {
  const { t, format } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();
  const invitations = useQuery({ queryKey: ["invitations"], queryFn: api.invitations });
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("reader");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [link, setLink] = useState<{ url: string; expires: string } | null>(null);
  const reload = () => queryClient.invalidateQueries({ queryKey: ["invitations"] });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = validate(z.object({ email: emailField(t), role: z.enum(["admin", "reviewer", "reader"]) }), { email, role });
    if (!result.ok) return setErrors(result.errors);
    setErrors({});
    try {
      const created = await api.invite(result.data);
      setEmail("");
      if (created.emailed) {
        toast(t.users.inviteSent(created.invitation.email));
        setLink(null);
      } else if (created.link) {
        setLink({ url: created.link, expires: format.dateTime(created.invitation.expires_at) });
      }
      await reload();
    } catch (caught) {
      setErrors({ email: caught instanceof Error ? caught.message : t.common.error });
    }
  };

  const cancel = async (id: number) => {
    await api.cancelInvitation(id);
    await reload();
  };

  const items = invitations.data ?? [];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.users.inviteTitle}</h2>
      </div>
      <div className="panel-body stack">
        <form className="actions-row" onSubmit={submit} noValidate>
          <label className={`field grow ${errors.email ? "field-invalid" : ""}`}>
            <span className="field-label">{t.users.email}</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="off" maxLength={254} />
            {errors.email && <span className="field-error">{errors.email}</span>}
          </label>
          <label className="field">
            <span className="field-label">{t.users.role}</span>
            <select value={role} onChange={(event) => setRole(event.target.value as Role)}>
              {ROLES.map((value) => (
                <option key={value} value={value}>
                  {t.roles[value]}
                </option>
              ))}
            </select>
          </label>
          <button className="button" type="submit">
            <Send size={16} strokeWidth={1.75} />
            {t.users.sendInvite}
          </button>
        </form>
        {link && <CopyLink link={link.url} note={`${t.users.linkReady} ${t.users.linkExpires(link.expires)}`} />}
      </div>
      <div className="panel-head">
        <h2>{t.users.invitations}</h2>
      </div>
      {items.length === 0 ? (
        <p className="panel-body muted flush">{t.users.noInvitations}</p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={item.id}>
              <span className={`status ${item.state === "used" ? "status-reviewed" : item.state === "active" ? "status-pending" : ""}`}>
                <span className="status-dot" aria-hidden="true" />
                {t.users.invitationStates[item.state] ?? item.state}
              </span>
              <span className={styles.email}>{item.email}</span>
              <span className="muted">
                {t.roles[item.role]} · {format.dateTime(item.created_at)}
                {item.invited_by ? ` · ${t.users.invitedBy(item.invited_by)}` : ""}
              </span>
              {item.state === "active" ? (
                <button className="icon-button" type="button" aria-label={t.users.cancelInvite} title={t.users.cancelInvite} onClick={() => cancel(item.id)}>
                  <X size={16} />
                </button>
              ) : (
                <span />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AccountRow({ account, self }: { account: Account; self: boolean }) {
  const { t, format } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [link, setLink] = useState<string | null>(null);
  const reload = () => queryClient.invalidateQueries({ queryKey: ["accounts"] });
  const run = async (action: () => Promise<unknown>, message: string) => {
    try {
      await action();
      toast(message);
      await reload();
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  const resetLink = async () => {
    try {
      const result = await api.accountResetLink(account.id);
      if (result.link) setLink(result.link);
      toast(result.detail, result.emailed ? "ok" : "error");
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };
  const name = account.name || account.email;
  return (
    <li className={styles.account}>
      <div className={styles.accountMain}>
        <strong>
          {name}
          {self && <span className="muted"> ({t.users.you})</span>}
        </strong>
        <span className="muted">{account.email}</span>
        <span className={styles.flags}>
          <span className={`status ${account.is_active ? "status-reviewed" : "status-danger"}`}>
            <span className="status-dot" aria-hidden="true" />
            {account.is_active ? t.users.active : t.users.inactive}
          </span>
          {account.locked && <span className="tag">{t.users.locked}</span>}
          {!account.email_verified && <span className="tag">{t.users.unverified}</span>}
          {account.two_factor_enabled && <span className="tag">{t.users.twoFactor}</span>}
          <span className="muted">
            {t.users.columns.lastLogin}: {account.last_login_at ? format.dateTime(account.last_login_at) : t.users.never}
          </span>
        </span>
      </div>
      <div className={styles.accountActions} aria-label={t.users.actionsFor(name)} role="group">
        <label className="field">
          <span className="visually-hidden">{t.users.role}</span>
          <select
            value={account.role}
            disabled={self}
            onChange={(event) => run(() => api.updateAccount(account.id, { role: event.target.value as Role }), t.users.updated)}
          >
            {ROLES.map((value) => (
              <option key={value} value={value}>
                {t.roles[value]}
              </option>
            ))}
          </select>
        </label>
        {account.locked && (
          <button className="button button-secondary" type="button" onClick={() => run(() => api.updateAccount(account.id, { unlock: true }), t.users.updated)}>
            {t.users.unlock}
          </button>
        )}
        <button className="button button-secondary" type="button" onClick={resetLink} disabled={!account.is_active}>
          {t.users.resetLink}
        </button>
        {!self && account.sessions > 0 && (
          <button className="button button-secondary" type="button" onClick={() => run(() => api.accountRevokeSessions(account.id), t.users.sessionsEnded(account.sessions))}>
            {t.users.endSessions}
          </button>
        )}
        {!self && account.two_factor_enabled && (
          <button className="button button-secondary" type="button" onClick={() => run(() => api.accountDisableTwoFactor(account.id), t.users.twoFactorRemoved)}>
            {t.users.removeTwoFactor}
          </button>
        )}
        {!self && (
          <button
            className={`button ${account.is_active ? "button-danger-ghost" : "button-secondary"}`}
            type="button"
            onClick={() => run(() => api.updateAccount(account.id, { is_active: !account.is_active }), t.users.updated)}
          >
            {account.is_active ? t.users.disable : t.users.enable}
          </button>
        )}
      </div>
      {link && <CopyLink link={link} note={t.users.linkReady} />}
    </li>
  );
}

export default function UsersPage() {
  const { t } = useLocale();
  const { user, can } = useSession();
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.accounts, enabled: can("users.manage") });
  if (!can("users.manage")) return <Forbidden />;
  return (
    <div className={page.page}>
      <PageHead title={t.users.title} description={t.users.description} />
      <div className={page.settings}>
        <InviteSection />
        <section className="panel">
          <div className="panel-head">
            <h2>{t.users.accounts}</h2>
          </div>
          <ul className={styles.list}>
            {(accounts.data ?? []).map((account) => (
              <AccountRow key={account.id} account={account} self={account.id === user.id} />
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
