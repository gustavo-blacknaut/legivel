"use client";

import { useQuery } from "@tanstack/react-query";
import { Info, Plus, ScanText, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Forbidden } from "@/components/Forbidden";
import { ModuleIcon, moduleName, useModules } from "@/components/Modules";
import { PageHead } from "@/components/PageHead";
import page from "@/components/Page.module.css";
import { PhotoInput, UploadChecklist, photoStyles } from "@/components/PhotoInput";
import styles from "@/components/Upload.module.css";
import { api } from "@/lib/api/endpoints";
import { useT } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import reading from "./reading.module.css";

export default function ReadingPage() {
  const t = useT();
  const { can } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const modules = useModules();
  const languages = useQuery({ queryKey: ["reading-languages"], queryFn: api.readingLanguages, staleTime: Infinity });
  const system = useQuery({ queryKey: ["system"], queryFn: api.system, staleTime: 60_000 });
  const [chosen, setChosen] = useState<string | null>(null);
  const [pages, setPages] = useState<(File | null)[]>([null]);
  const [language, setLanguage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!can("documents.upload")) return <Forbidden />;

  const available = modules.data ?? [];
  const requested = params.get("modulo");
  const selectedKey = chosen ?? (available.some((module) => module.key === requested) ? requested : available[0]?.key) ?? null;
  const selected = available.find((module) => module.key === selectedKey);
  const files = pages.filter((file): file is File => file !== null);

  const choose = (key: string) => {
    setChosen(key);
    const limit = available.find((module) => module.key === key)?.max_pages ?? 1;
    setPages((current) => (current.length > limit ? current.slice(0, limit) : current));
  };

  const setPage = (index: number, file: File | null) =>
    setPages((current) => {
      const next = [...current];
      next[index] = file;
      if (file === null && next.length > 1) next.splice(index, 1);
      return next;
    });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || files.length === 0) {
      setError(t.reading.noPages);
      return;
    }
    const form = new FormData();
    form.append("module", selected.key);
    if (language) form.append("language", language);
    for (const file of files) form.append("pages", file);
    setBusy(true);
    setError(null);
    try {
      const record = await api.uploadRecord(form);
      router.push(`/registros/${record.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t.common.error);
      setBusy(false);
    }
  };

  return (
    <div className={page.page}>
      <PageHead title={t.reading.title} description={t.reading.description} />
      <form className={styles.stack} onSubmit={submit}>
        <fieldset className={reading.modules}>
          <legend className="visually-hidden">{t.reading.chooseModule}</legend>
          {available.map((module) => (
            <label key={module.key} className={`${reading.module} ${module.key === selectedKey ? reading.active : ""}`}>
              <input type="radio" name="module" value={module.key} checked={module.key === selectedKey} onChange={() => choose(module.key)} />
              <span className={reading.icon}>
                <ModuleIcon module={module.key} size={20} />
              </span>
              <span className={reading.text}>
                <strong>{moduleName(t, module)}</strong>
                <span>{t.modules.descriptions[module.key] ?? module.description}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {selected && (
          <section className="panel">
            <div className="panel-head">
              <h2>{t.reading.pages}</h2>
              <span className="muted">{t.reading.limit(selected.max_pages)}</span>
            </div>
            <div className="panel-body stack">
              {error && (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              )}
              {selected.key === "cards" && (
                <div className="alert alert-warning">
                  <Info size={16} />
                  {t.reading.cardNote}
                </div>
              )}
              <div className={photoStyles.grid}>
                {pages.map((file, index) => (
                  <PhotoInput
                    key={index}
                    label={selected.page_labels[index] ?? t.reading.pageLabel(index + 1)}
                    file={file}
                    onChange={(next) => setPage(index, next)}
                  />
                ))}
              </div>
              {selected.multi_page && pages.length < selected.max_pages && pages.every(Boolean) && (
                <div>
                  <button className="button button-secondary" type="button" onClick={() => setPages((current) => [...current, null])}>
                    <Plus size={16} strokeWidth={1.75} />
                    {t.reading.addPage}
                  </button>
                </div>
              )}
              <label className={`field ${reading.language}`}>
                <span className="field-label">{t.reading.language}</span>
                <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                  <option value="">{t.reading.autoLanguage}</option>
                  {languages.data?.map((item) => (
                    <option key={item.code} value={item.code}>
                      {t.settings.languageNames[item.code] ?? item.name}
                    </option>
                  ))}
                </select>
              </label>
              <UploadChecklist items={t.upload.checklist} />
            </div>
            <div className={`panel-foot ${styles.footer}`}>
              <span className={styles.note}>
                <ShieldCheck size={14} strokeWidth={1.75} />
                {system.data?.encrypted_storage === false ? t.upload.plain : t.upload.encrypted}
              </span>
              <button className="button button-lg" type="submit" disabled={busy || files.length === 0}>
                <ScanText size={18} strokeWidth={1.75} />
                {t.reading.submit}
              </button>
            </div>
          </section>
        )}
      </form>
      {busy && (
        <div className={styles.processing} role="status">
          <div className={styles.card}>
            <span className="spinner" />
            <span>
              <strong>{t.reading.processingTitle}</strong>
              <span>{t.reading.processingText}</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
