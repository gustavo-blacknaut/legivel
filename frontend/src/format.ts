export type ConfidenceLevel = "high" | "medium" | "low" | "unknown";

const HIGH_CONFIDENCE = 0.9;
const MEDIUM_CONFIDENCE = 0.75;

export const DOCUMENT_TYPE_LABELS: Record<string, string> = { rg: "RG", cnh: "CNH", cpf: "CPF" };

export const STATUS_LABELS: Record<string, string> = {
  pending_review: "Pendente de revisão",
  reviewed: "Revisado",
};

export function confidenceLevel(confidence: number | null | undefined): ConfidenceLevel {
  if (confidence === null || confidence === undefined) return "unknown";
  if (confidence >= HIGH_CONFIDENCE) return "high";
  return confidence >= MEDIUM_CONFIDENCE ? "medium" : "low";
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatCpf(cpf: string | null): string {
  if (!cpf || cpf.length !== 11) return cpf ?? "";
  return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9)}`;
}

export function initials(name: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

let currentTimeZone = "America/Sao_Paulo";

export function setTimeZone(timeZone: string): void {
  currentTimeZone = timeZone;
}

export function getTimeZone(): string {
  return currentTimeZone;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: currentTimeZone,
  });
}

export function formatDateTime(iso: string, withSeconds = false): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: withSeconds ? "2-digit" : undefined,
    timeZone: currentTimeZone,
  });
}

export function plural(count: number, singular: string, pluralForm: string): string {
  return `${count.toLocaleString("pt-BR")} ${count === 1 ? singular : pluralForm}`;
}

export function describeDevice(userAgent: string | null): string {
  if (!userAgent) return "Dispositivo desconhecido";
  const browser = /Edg\//.test(userAgent)
    ? "Edge"
    : /Chrome\//.test(userAgent)
      ? "Chrome"
      : /Firefox\//.test(userAgent)
        ? "Firefox"
        : /Safari\//.test(userAgent)
          ? "Safari"
          : "Navegador";
  const system = /Android/.test(userAgent)
    ? "Android"
    : /iPhone|iPad/.test(userAgent)
      ? "iOS"
      : /Windows/.test(userAgent)
        ? "Windows"
        : /Mac OS/.test(userAgent)
          ? "macOS"
          : /Linux/.test(userAgent)
            ? "Linux"
            : "sistema desconhecido";
  return `${browser} · ${system}`;
}
