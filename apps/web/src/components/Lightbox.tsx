"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useT } from "@/lib/i18n";
import styles from "./Review.module.css";

export function Lightbox({ src, onClose }: { src: string | null; onClose: () => void }) {
  const t = useT();
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!src) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    close.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") { event.preventDefault(); close.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = overflow; previous?.focus(); };
  }, [src, onClose]);
  if (!src) return null;
  return createPortal(
    <div className={styles.lightbox} onClick={onClose} role="dialog" aria-modal="true" aria-label={t.review.enlarged}>
      <button ref={close} className={`icon-button ${styles.lightboxClose}`} type="button" aria-label={t.common.close} onClick={onClose}>
        <X size={20} />
      </button>
      <img src={src} alt={t.review.enlarged} onClick={(event) => event.stopPropagation()} />
    </div>,
    document.body,
  );
}
