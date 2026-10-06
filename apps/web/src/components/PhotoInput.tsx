"use client";

import { Camera, Check, ImagePlus, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useT } from "@/lib/i18n";
import { useInstance } from "./Providers";
import styles from "./PhotoInput.module.css";

const MIME_FORMATS: Record<string, string> = {
  "image/jpeg": "jpeg",
  "image/png": "png",
  "image/webp": "webp",
  "image/heic": "heic",
  "image/heif": "heic",
};
const EXTENSION_FORMATS: Record<string, string> = { jpg: "jpeg", jpeg: "jpeg", png: "png", webp: "webp", heic: "heic", heif: "heic" };
export const FORMAT_LABELS: Record<string, string> = { jpeg: "JPEG", png: "PNG", webp: "WebP", heic: "HEIC" };

export function fileFormat(file: File): string | null {
  const byMime = MIME_FORMATS[file.type];
  if (byMime) return byMime;
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_FORMATS[extension] ?? null;
}

export function checkFile(file: File, formats: string[], maxMb: number): "format" | "size" | null {
  const format = fileFormat(file);
  if (!format || !formats.includes(format)) return "format";
  if (file.size > maxMb * 1024 * 1024) return "size";
  return null;
}

type PhotoInputProps = { label: string; file: File | null; onChange: (file: File | null) => void };

export function PhotoInput({ label, file, onChange }: PhotoInputProps) {
  const t = useT();
  const instance = useInstance();
  const cameraRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const formats = instance.upload_formats;
  const accept = formats.map((format) => (format === "heic" ? "image/heic,image/heif,.heic" : `image/${format}`)).join(",");
  const formatNames = formats.map((format) => FORMAT_LABELS[format] ?? format).join(", ");

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const pick = (picked: File | null | undefined) => {
    if (!picked) return;
    const problem = checkFile(picked, formats, instance.upload_max_mb);
    if (problem === "format") {
      setError(t.upload.wrongFormat(formatNames));
      return;
    }
    if (problem === "size") {
      setError(t.upload.tooLarge(instance.upload_max_mb));
      return;
    }
    setError(null);
    onChange(picked);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files[0]);
  };

  const inputs = (
    <>
      <input
        ref={cameraRef}
        className={styles.hidden}
        type="file"
        accept={accept}
        capture="environment"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          pick(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <input
        ref={fileRef}
        className={styles.hidden}
        type="file"
        accept={accept}
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          pick(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </>
  );

  if (preview) {
    return (
      <div className={`${styles.zone} ${styles.filled}`}>
        {inputs}
        <span className={styles.badge}>{label}</span>
        <img className={styles.preview} src={preview} alt={label} />
        <div className={styles.bar}>
          <button className="button button-secondary" type="button" onClick={() => cameraRef.current?.click()}>
            <Camera size={16} strokeWidth={1.75} />
            {t.upload.replace}
          </button>
          <button className="button button-ghost" type="button" onClick={() => onChange(null)}>
            <X size={16} strokeWidth={1.75} />
            {t.upload.remove}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`${styles.zone} ${dragging ? styles.dragging : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      {inputs}
      <ImagePlus size={28} strokeWidth={1.5} aria-hidden="true" />
      <span className={styles.title}>{label}</span>
      <div className={styles.buttons}>
        <button className="button" type="button" onClick={() => cameraRef.current?.click()} aria-label={`${label}: ${t.upload.takePhoto}`}>
          <Camera size={16} strokeWidth={1.75} />
          {t.upload.takePhoto}
        </button>
        <button className="button button-secondary" type="button" onClick={() => fileRef.current?.click()} aria-label={`${label}: ${t.upload.chooseFile}`}>
          <ImagePlus size={16} strokeWidth={1.75} />
          {t.upload.chooseFile}
        </button>
      </div>
      {error && <span className={styles.error} role="alert">{error}</span>}
    </div>
  );
}

export function UploadChecklist({ items }: { items: string[] }) {
  const instance = useInstance();
  const t = useT();
  const formatNames = instance.upload_formats.map((format) => FORMAT_LABELS[format] ?? format).join(", ");
  return (
    <>
      <ul className={styles.checklist}>
        {items.map((item) => (
          <li key={item}>
            <Check size={16} strokeWidth={2} />
            {item}
          </li>
        ))}
      </ul>
      <p className={styles.formats}>{t.upload.formats(formatNames, instance.upload_max_mb)}</p>
    </>
  );
}

export { styles as photoStyles };
