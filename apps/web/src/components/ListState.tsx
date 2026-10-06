"use client";

import { FilterX, type LucideIcon } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { useT } from "@/lib/i18n";
import styles from "./ListState.module.css";

type ListBarProps = { total: number | null; one: string; many: string; filtered: boolean; onClear: () => void };

export function ListBar({ total, one, many, filtered, onClear }: ListBarProps) {
  const t = useT();
  return (
    <div className={styles.bar} aria-live="polite">
      <span>
        {total === null ? t.common.loading : <strong>{t.list.count(total, one, many)}</strong>}
        {filtered && total !== null && t.list.filtered}
      </span>
      {filtered && (
        <button className="button button-ghost" type="button" onClick={onClear}>
          <FilterX size={16} strokeWidth={1.75} />
          {t.list.clear}
        </button>
      )}
    </div>
  );
}

type EmptyStateProps = { icon: LucideIcon; title: string; text: string; action?: ReactNode };

export function EmptyState({ icon: Icon, title, text, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <span className={styles.icon} aria-hidden="true">
        <Icon size={22} strokeWidth={1.5} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}

export function SkeletonRows({ count = 8 }: { count?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className={styles.skeleton} />
      ))}
    </div>
  );
}

type LoadMoreProps = { onVisible: () => void; enabled: boolean; loading: boolean; error?: string | null };

export function LoadMore({ onVisible, enabled, loading, error }: LoadMoreProps) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const callback = useRef(onVisible);
  useEffect(() => {
    callback.current = onVisible;
  }, [onVisible]);
  useEffect(() => {
    const element = ref.current;
    if (!element || !enabled) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) callback.current();
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [enabled]);
  return (
    <>
      <div ref={ref} className={styles.sentinel} />
      {loading && <div className={styles.more}>{t.common.loadingMore}</div>}
      {error && <div className={styles.more}>{error}</div>}
    </>
  );
}
