import { FilterX, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { plural } from "../format";

type ListBarProps = {
  total: number | null;
  singular: string;
  pluralLabel: string;
  filtered: boolean;
  onClear: () => void;
};

export function ListBar({ total, singular, pluralLabel, filtered, onClear }: ListBarProps) {
  return (
    <div className="list-bar" aria-live="polite">
      <span>
        {total === null ? "Carregando…" : <strong>{plural(total, singular, pluralLabel)}</strong>}
        {filtered && total !== null && " com os filtros aplicados"}
      </span>
      {filtered && (
        <button className="button button-ghost" type="button" onClick={onClear}>
          <FilterX size={16} strokeWidth={1.75} />
          Limpar filtros
        </button>
      )}
    </div>
  );
}

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  text: string;
  action?: ReactNode;
};

export function EmptyState({ icon: Icon, title, text, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <span className="empty-icon" aria-hidden="true">
        <Icon size={22} strokeWidth={1.5} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

export function SkeletonRows({ count = 8 }: { count?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="skeleton" />
      ))}
    </div>
  );
}
