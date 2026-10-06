"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Link2, Send, Share2, X } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { z } from "zod";
import { api, type ScanLinkCreated } from "@/lib/api/endpoints";
import { useLocale } from "@/lib/i18n";
import { useBrowserValue } from "@/lib/storage";
import { useToast } from "./Toast";
import styles from "./Upload.module.css";

const VALIDITY_HOURS = [24, 48, 168];
const REFRESH_MS = 8000;
const schema = z.object({ label: z.string().trim().max(120), hours: z.number().int().min(1).max(336) });

export function ScanLinks() {
  const { t, format } = useLocale();
  const toast = useToast();
  const queryClient = useQueryClient();
  const links = useQuery({ queryKey: ["scan-links"], queryFn: api.scanLinks, refetchInterval: REFRESH_MS });
  const [creating, setCreating] = useState(false);
  const [label, setLabel] = useState("");
  const [hours, setHours] = useState(48);
  const [created, setCreated] = useState<ScanLinkCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const canShare = useBrowserValue(() => "share" in navigator, false);
  const urlOf = (token: string) => `${window.location.origin}/enviar/${token}`;

  const create = async (event: FormEvent) => {
    event.preventDefault();
    const parsed = schema.safeParse({ label, hours });
    if (!parsed.success) {
      toast(t.validation.tooLong(120), "error");
      return;
    }
    try {
      const result = await api.createScanLink(parsed.data.label, parsed.data.hours);
      setCreated(result);
      setCopied(false);
      setLabel("");
      setCreating(false);
      await queryClient.invalidateQueries({ queryKey: ["scan-links"] });
    } catch (caught) {
      toast(caught instanceof Error ? caught.message : t.common.error, "error");
    }
  };

  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      toast(t.scanLinks.copyManually, "error");
    }
  };

  const share = async (url: string) => {
    try {
      await navigator.share({ title: t.scanLinks.shareTitle, text: t.scanLinks.shareText, url });
    } catch {
      return;
    }
  };

  const revoke = async (id: number) => {
    await api.revokeScanLink(id);
    toast(t.scanLinks.cancelled);
    await queryClient.invalidateQueries({ queryKey: ["scan-links"] });
  };

  const items = links.data ?? [];

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{t.scanLinks.title}</h2>
        {!creating && (
          <button className="button button-secondary" type="button" onClick={() => setCreating(true)}>
            <Link2 size={16} strokeWidth={1.75} />
            {t.scanLinks.create}
          </button>
        )}
      </div>
      <div className="panel-body stack">
        <p className="muted flush">{t.scanLinks.intro}</p>
        {creating && (
          <form className="actions-row" onSubmit={create}>
            <label className="field grow">
              <span className="field-label">
                {t.scanLinks.label} <span className="muted">({t.common.optional})</span>
              </span>
              <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder={t.scanLinks.labelPlaceholder} maxLength={120} />
            </label>
            <label className="field">
              <span className="field-label">{t.scanLinks.validity}</span>
              <select value={hours} onChange={(event) => setHours(Number(event.target.value))}>
                {VALIDITY_HOURS.map((value) => (
                  <option key={value} value={value}>
                    {t.scanLinks.hours(value)}
                  </option>
                ))}
              </select>
            </label>
            <button className="button" type="submit">
              <Send size={16} strokeWidth={1.75} />
              {t.scanLinks.generate}
            </button>
            <button className="button button-ghost" type="button" onClick={() => setCreating(false)}>
              {t.common.cancel}
            </button>
          </form>
        )}
        {created && (
          <div className={styles.result}>
            <span className="field-label">{t.scanLinks.result(created.label, format.dateTime(created.expires_at))}</span>
            <div className={styles.linkBox}>
              <input readOnly value={urlOf(created.token)} onFocus={(event) => event.target.select()} aria-label={t.scanLinks.linkAria} className="mono" />
              <button className="button" type="button" onClick={() => copy(urlOf(created.token))}>
                {copied ? <Check size={16} /> : <Copy size={16} strokeWidth={1.75} />}
                {copied ? t.common.copied : t.common.copy}
              </button>
              {canShare && (
                <button className="button button-secondary" type="button" onClick={() => share(urlOf(created.token))}>
                  <Share2 size={16} strokeWidth={1.75} />
                  {t.common.share}
                </button>
              )}
            </div>
            <span className="field-hint">{t.scanLinks.onlyNow}</span>
          </div>
        )}
      </div>
      {items.length > 0 && (
        <ul className={styles.links}>
          {items.map((link) => (
            <li key={link.id}>
              <span className={`status ${link.state === "used" ? "status-reviewed" : link.state === "active" ? "status-pending" : ""}`}>
                <span className="status-dot" aria-hidden="true" />
                {t.scanLinks.states[link.state as keyof typeof t.scanLinks.states] ?? link.state}
              </span>
              <span className={styles.label}>{link.label || t.scanLinks.fallbackLabel(link.id)}</span>
              <span className={`muted ${styles.date}`}>
                {link.used_at ? t.scanLinks.receivedAt(format.dateTime(link.used_at)) : t.scanLinks.validUntil(format.dateTime(link.expires_at))}
              </span>
              {link.document_id ? (
                <Link href={`/documentos/${link.document_id}`} className="button button-ghost">
                  {t.scanLinks.openDocument}
                </Link>
              ) : link.state === "active" ? (
                <button className="icon-button" type="button" aria-label={t.scanLinks.cancel} title={t.scanLinks.cancel} onClick={() => revoke(link.id)}>
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
