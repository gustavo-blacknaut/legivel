"use client";

import { confidenceLevel, formatPercent } from "@/lib/format";
import { useT } from "@/lib/i18n";

export function StatusLabel({ status }: { status: string | null | undefined }) {
  const t = useT();
  if (!status) return <span className="status muted">{t.status.none}</span>;
  const tone = status === "reviewed" ? "status-reviewed" : "status-pending";
  const label = status === "reviewed" ? t.status.reviewed : status === "pending_review" ? t.status.pending_review : status;
  return (
    <span className={`status ${tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export function Confidence({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="confidence muted">—</span>;
  return <span className={`confidence confidence-${confidenceLevel(value)}`}>{formatPercent(value)}</span>;
}
