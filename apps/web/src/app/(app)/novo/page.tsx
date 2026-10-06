"use client";

import { ScanText, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Forbidden } from "@/components/Forbidden";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { PhotoInput, UploadChecklist, photoStyles } from "@/components/PhotoInput";
import { ScanLinks } from "@/components/ScanLinks";
import styles from "@/components/Upload.module.css";
import { api } from "@/lib/api/endpoints";
import { useT } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export default function UploadPage() {
  const t = useT();
  const { can } = useSession();
  const router = useRouter();
  const [front, setFront] = useState<File | null>(null);
  const [back, setBack] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const system = useQuery({ queryKey: ["system"], queryFn: api.system, staleTime: 60_000 });

  if (!can("documents.upload")) {
    return <Forbidden />;
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const form = new FormData();
    if (front) form.append("front", front);
    if (back) form.append("back", back);
    setBusy(true);
    setError(null);
    try {
      const document = await api.upload(form);
      router.push(`/documentos/${document.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
    }
  };

  return (
    <div className={page.page}>
      <PageHead title={t.upload.title} description={t.upload.description} />
      <div className={styles.stack}>
        <form className="panel" onSubmit={submit}>
          <div className="panel-body">
            {error && (
              <div className="alert alert-danger" role="alert">
                {error}
              </div>
            )}
            <div className={photoStyles.grid}>
              <PhotoInput label={t.upload.front} file={front} onChange={setFront} />
              <PhotoInput label={t.upload.back} file={back} onChange={setBack} />
            </div>
            <UploadChecklist items={t.upload.checklist} />
          </div>
          <div className={`panel-foot ${styles.footer}`}>
            <span className={styles.note}>
              <ShieldCheck size={14} strokeWidth={1.75} />
              {system.data?.encrypted_storage === false ? t.upload.plain : t.upload.encrypted}
            </span>
            <button className="button button-lg" type="submit" disabled={busy || (!front && !back)}>
              <ScanText size={18} strokeWidth={1.75} />
              {t.upload.submit}
            </button>
          </div>
        </form>
        {can("scan_links.manage") && <ScanLinks />}
      </div>
      {busy && (
        <div className={styles.processing} role="status">
          <div className={styles.card}>
            <span className="spinner" />
            <span>
              <strong>{t.upload.processingTitle}</strong>
              <span>{t.upload.processingText}</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
