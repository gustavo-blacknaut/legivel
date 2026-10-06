"use client";

import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import styles from "./Dialog.module.css";

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

type DialogProps = {
  open: boolean;
  title: string;
  icon?: ReactNode;
  role?: "dialog" | "alertdialog";
  wide?: boolean;
  large?: boolean;
  busy?: boolean;
  initialFocus?: string;
  onClose: () => void;
  children: ReactNode;
  actions: ReactNode;
};

export function Dialog({ open, title, icon, role = "dialog", wide, large, busy, initialFocus, onClose, children, actions }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const target = ref.current?.querySelector<HTMLElement>(initialFocus ?? FOCUSABLE);
    target?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open, initialFocus]);

  if (!open) return null;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape" && !busy) {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !ref.current) return;
    const focusable = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return createPortal(
    <div className={styles.backdrop} onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <div
        ref={ref}
        className={`${styles.dialog} ${wide ? styles.wide : ""} ${large ? styles.large : ""}`}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
      >
        <span className={styles.handle} aria-hidden="true" />
        <div className={styles.body}>
          {icon && (
            <span className={styles.icon} aria-hidden="true">
              {icon}
            </span>
          )}
          <h2 id={titleId}>{title}</h2>
          {children}
        </div>
        <div className={styles.actions}>{actions}</div>
      </div>
    </div>,
    document.body,
  );
}

export { styles as dialogStyles };
