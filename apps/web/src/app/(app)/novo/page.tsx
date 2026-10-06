"use client";

import { ScanText, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Forbidden } from "@/components/Forbidden";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { PhotoInput, UploadChecklist, photoStyles, checkFile, FORMAT_LABELS } from "@/components/PhotoInput";
import { Dialog } from "@/components/Dialog";
import Link from "next/link";
import { DuplicateError, enqueue } from "@/lib/workflow";
import { useWorkflowText } from "@/lib/workflow-text";
import { ScanLinks } from "@/components/ScanLinks";
import styles from "@/components/Upload.module.css";
import { api } from "@/lib/api/endpoints";
import { useT } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export default function UploadPage() {
  const t = useT();
  const w = useWorkflowText();
  const [duplicateId, setDuplicateId] = useState<number | null>(null);
  const [batch, setBatch] = useState<File[]>([]);
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

  const submit = async (event?: FormEvent, duplicate = "ask") => {
    event?.preventDefault();
    const form = new FormData();
    if (front) form.append("front", front);
    if (back) form.append("back", back);
    form.append("duplicate", duplicate);
    setBusy(true);
    setDuplicateId(null);
    setError(null);
    try {
      if (batch.length) {
        for (const file of batch) {
          const entry = new FormData(); entry.append("front", file); entry.append("duplicate", "keep");
          await enqueue(entry);
          setBatch((current) => current.filter((item) => item !== file));
        }
        router.push("/fila");
      } else if (system.data?.encrypted_storage === false) {
        const document = await api.upload(form);
        router.push(`/documentos/${document.id}`);
      } else {
        const job = await enqueue(form);
        router.push(job.status === "completed" ? `/documentos/${job.result_id}` : "/fila");
      }
    } catch (caught) {
      if (caught instanceof DuplicateError) setDuplicateId(caught.documentId);
      else setError(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
    }
  };

  return (
    <div className={page.page}>
      <PageHead title={t.upload.title} description={t.upload.description} />
      <div className={styles.stack}>
        <form className="panel" onSubmit={(event) => void submit(event)}>
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
            <label className="field"><span className="field-label">{w.batch}</span>
              <input type="file" accept="image/jpeg,image/png,image/webp,.heic,.heif" multiple disabled={busy || system.data?.encrypted_storage === false} onChange={(event) => {
                const picked = Array.from(event.target.files ?? []);
                if (picked.length > 50) { setError("Máximo de 50 arquivos por lote."); return; }
                const rejected = picked.find((file) => checkFile(file, system.data?.upload_formats ?? ["jpeg", "png", "webp", "heic"], system.data?.upload_max_mb ?? 15));
                if (rejected) {
                  const problem = checkFile(rejected, system.data?.upload_formats ?? ["jpeg", "png", "webp", "heic"], system.data?.upload_max_mb ?? 15);
                  setError(problem === "size" ? t.upload.tooLarge(system.data?.upload_max_mb ?? 15) : t.upload.wrongFormat((system.data?.upload_formats ?? []).map((format) => FORMAT_LABELS[format] ?? format).join(", ")));
                  return;
                }
                setError(null); setBatch(picked); setFront(null); setBack(null);
              }} />
              <small>{w.batchHint}</small>
            </label>
            {batch.length > 0 && <p>{batch.length} <button className="button button-ghost" type="button" onClick={() => setBatch([])}>{w.clear}</button></p>}
          </div>
          <div className={`panel-foot ${styles.footer}`}>
            <span className={styles.note}>
              <ShieldCheck size={14} strokeWidth={1.75} />
              {system.data?.encrypted_storage === false ? t.upload.plain : t.upload.encrypted}
            </span>
            <button className="button button-lg" type="submit" disabled={busy || (!front && !back && !batch.length)}>
              <ScanText size={18} strokeWidth={1.75} />
              {t.upload.submit}
            </button>
          </div>
        </form>
        {can("scan_links.manage") && <ScanLinks />}
      </div>
      <Dialog open={duplicateId !== null} title={w.duplicate} onClose={() => setDuplicateId(null)} actions={<>
        <button className="button button-secondary" type="button" onClick={() => setDuplicateId(null)}>{w.cancel}</button>
        <button className="button" type="button" onClick={() => void submit(undefined, "keep")}>{w.keep}</button>
        {can("documents.delete") && <button className="button button-secondary" type="button" onClick={() => void submit(undefined, "replace")}>{w.replace}</button>}
      </>}>
        <p>{w.duplicateHint}</p><Link href={`/documentos/${duplicateId}`} className="button button-secondary">{w.link}</Link>
      </Dialog>
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
