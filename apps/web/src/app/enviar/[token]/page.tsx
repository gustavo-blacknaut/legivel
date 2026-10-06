"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Lock, ScanText } from "lucide-react";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Brand } from "@/components/Brand";
import { PhotoInput, UploadChecklist, photoStyles } from "@/components/PhotoInput";
import upload from "@/components/Upload.module.css";
import { api } from "@/lib/api/endpoints";
import { useT } from "@/lib/i18n";
import styles from "./public.module.css";

export default function PublicScanPage() {
  const t = useT();
  const token = useParams<{ token: string }>().token;
  const link = useQuery({ queryKey: ["public-link", token], queryFn: () => api.publicLink(token), retry: false });
  const [front, setFront] = useState<File | null>(null);
  const [back, setBack] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const form = new FormData();
    if (front) form.append("front", front);
    if (back) form.append("back", back);
    setSending(true);
    setError(null);
    try {
      await api.publicUpload(token, form);
      setDone(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.common.error);
    } finally {
      setSending(false);
    }
  };

  const unavailable = link.isError || (link.data && link.data.state !== "active");

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Brand className={styles.brand} />
      </header>
      <div className={styles.content}>
        {link.isPending && <div className="spinner spinner-page" role="status" />}
        {!done && unavailable && (
          <div className={styles.message}>
            <CircleAlert size={32} strokeWidth={1.5} />
            <h1>{t.publicScan.unavailableTitle}</h1>
            <p>{t.publicScan.unavailableText}</p>
          </div>
        )}
        {done && (
          <div className={`${styles.message} ${styles.success}`}>
            <CircleCheck size={32} strokeWidth={1.5} />
            <h1>{t.publicScan.doneTitle}</h1>
            <p>{t.publicScan.doneText}</p>
          </div>
        )}
        {!done && link.data?.state === "active" && (
          <form className="panel" onSubmit={submit}>
            <div className="panel-body stack">
              <div>
                <h1 className={styles.title}>{t.publicScan.title}</h1>
                <p className="muted flush">
                  {link.data.label ? `${link.data.label}. ` : ""}
                  {t.publicScan.intro}
                </p>
              </div>
              {error && (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              )}
              <div className={photoStyles.grid}>
                <PhotoInput label={t.upload.front} file={front} onChange={setFront} />
                <PhotoInput label={t.upload.back} file={back} onChange={setBack} />
              </div>
              <UploadChecklist items={t.upload.checklist.slice(0, 2)} />
            </div>
            <div className={`panel-foot ${upload.footer}`}>
              <span className={upload.note}>
                <Lock size={14} strokeWidth={1.75} />
                {t.publicScan.note}
              </span>
              <button className="button button-lg" type="submit" disabled={sending || (!front && !back)}>
                <ScanText size={18} strokeWidth={1.75} />
                {sending ? t.publicScan.sending : t.publicScan.submit}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
