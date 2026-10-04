import { confidenceLevel, formatPercent, STATUS_LABELS } from "../format";

export function StatusLabel({ status }: { status: string | null }) {
  if (!status) return <span className="status muted">Sem documentos</span>;
  const tone = status === "reviewed" ? "status-reviewed" : "status-pending";
  return (
    <span className={`status ${tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function Confidence({ value }: { value: number | null }) {
  if (value === null) return <span className="confidence muted">—</span>;
  return <span className={`confidence confidence-${confidenceLevel(value)}`}>{formatPercent(value)}</span>;
}
