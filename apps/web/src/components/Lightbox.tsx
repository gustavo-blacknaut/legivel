"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useT } from "@/lib/i18n";
import styles from "./Review.module.css";

export function Lightbox({ src, onClose }: { src: string | null; onClose: () => void }) {
  const t = useT();
  useEffect(() => {
    if (!src) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [src, onClose]);
  if (!src) return null;
  return createPortal(
    <div className={styles.lightbox} onClick={onClose} role="dialog" aria-modal="true" aria-label={t.review.enlarged}>
      <button className={`icon-button ${styles.lightboxClose}`} type="button" aria-label={t.common.close} autoFocus onClick={onClose}>
        <X size={20} />
      </button>
      <img src={src} alt="" onClick={(event) => event.stopPropagation()} />
    </div>,
    document.body,
  );
}
