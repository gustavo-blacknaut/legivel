export type Language = "pt-BR" | "en";
export type ConfidenceLevel = "high" | "medium" | "low" | "unknown";

const HIGH_CONFIDENCE = 0.9;
const MEDIUM_CONFIDENCE = 0.75;

export function confidenceLevel(confidence: number | null | undefined): ConfidenceLevel {
  if (confidence === null || confidence === undefined) return "unknown";
  if (confidence >= HIGH_CONFIDENCE) return "high";
  return confidence >= MEDIUM_CONFIDENCE ? "medium" : "low";
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatCpf(cpf: string | null | undefined): string {
  if (!cpf || cpf.length !== 11) return cpf ?? "";
  return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9)}`;
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase() || "?";
}

export function normalizeForMatch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[.\-\s/]/g, "")
    .toUpperCase();
}

export type Formatter = {
  date: (iso: string) => string;
  dateTime: (iso: string, withSeconds?: boolean) => string;
  number: (value: number) => string;
};

export function createFormatter(language: Language, timeZone: string): Formatter {
  return {
    date: (iso) =>
      new Date(iso).toLocaleDateString(language, { day: "2-digit", month: "2-digit", year: "numeric", timeZone }),
    dateTime: (iso, withSeconds = false) =>
      new Date(iso).toLocaleString(language, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: withSeconds ? "2-digit" : undefined,
        timeZone,
      }),
    number: (value) => value.toLocaleString(language),
  };
}

export function describeDevice(userAgent: string | null | undefined, unknown: string): string {
  if (!userAgent) return unknown;
  const browser = /Edg\//.test(userAgent)
    ? "Edge"
    : /Firefox\//.test(userAgent)
      ? "Firefox"
      : /Chrome\//.test(userAgent)
        ? "Chrome"
        : /Safari\//.test(userAgent)
          ? "Safari"
          : "Browser";
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
            : "?";
  return `${browser} · ${system}`;
}
