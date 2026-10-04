import type {
  AuditEntry,
  DocumentDetail,
  DocumentSummary,
  DocumentType,
  PageResult,
  Person,
  PersonDetail,
  PublicLink,
  ScanLink,
  ScanLinkCreated,
  SessionInfo,
  Settings,
  SystemInfo,
  User,
  Verification,
} from "./types";

export const UNAUTHORIZED_EVENT = "registra:unauthorized";
const NO_RETRY_PATHS = ["/api/auth/login", "/api/auth/refresh", "/api/auth/logout", "/api/public/"];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/api/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-Requested-With": "green-ocr" },
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("X-Requested-With", "green-ocr");
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(path, { ...init, headers, credentials: "same-origin" });
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await send(path, init);
  const canRetry = !NO_RETRY_PATHS.some((prefix) => path.startsWith(prefix));
  if (response.status === 401 && canRetry) {
    if (await refreshSession()) {
      response = await send(path, init);
    }
    if (response.status === 401 && path !== "/api/auth/me") {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : "Algo deu errado. Tente novamente.";
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function withQuery(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export const api = {
  me: () => request<User>("/api/auth/me"),
  login: (username: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  sessions: () => request<SessionInfo[]>("/api/auth/sessions"),
  revokeOtherSessions: () => request<{ revoked: number }>("/api/auth/sessions/revoke-others", { method: "POST" }),
  system: () => request<SystemInfo>("/api/system"),
  settings: () => request<Settings>("/api/settings"),
  saveSettings: (settings: Settings) => request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(settings) }),
  timezones: () => request<string[]>("/api/settings/timezones"),
  documentTypes: () => request<DocumentType[]>("/api/document-types"),
  people: (params: URLSearchParams) => request<PageResult<Person>>(withQuery("/api/people", params)),
  person: (id: number) => request<PersonDetail>(`/api/people/${id}`),
  updatePerson: (id: number, values: Record<string, string | null>) =>
    request<PersonDetail>(`/api/people/${id}`, { method: "PUT", body: JSON.stringify({ values }) }),
  verifyPerson: (id: number) => request<Verification>(`/api/people/${id}/verify`, { method: "POST" }),
  deletePerson: (id: number) => request<void>(`/api/people/${id}`, { method: "DELETE" }),
  documents: (params: URLSearchParams) => request<PageResult<DocumentSummary>>(withQuery("/api/documents", params)),
  document: (id: number) => request<DocumentDetail>(`/api/documents/${id}`),
  upload: (form: FormData) => request<DocumentDetail>("/api/documents", { method: "POST", body: form }),
  saveDocument: (id: number, values: Record<string, string>) =>
    request<DocumentDetail>(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify({ values }) }),
  reprocess: (id: number, docType: string | null) =>
    request<DocumentDetail>(`/api/documents/${id}/reprocess`, {
      method: "POST",
      body: JSON.stringify({ doc_type: docType }),
    }),
  deleteDocument: (id: number) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  audit: (params: URLSearchParams) => request<PageResult<AuditEntry>>(withQuery("/api/audit", params)),
  scanLinks: () => request<ScanLink[]>("/api/scan-links"),
  createScanLink: (label: string, hours: number) =>
    request<ScanLinkCreated>("/api/scan-links", { method: "POST", body: JSON.stringify({ label, hours }) }),
  revokeScanLink: (id: number) => request<void>(`/api/scan-links/${id}`, { method: "DELETE" }),
  publicLink: (token: string) => request<PublicLink>(`/api/public/scan/${encodeURIComponent(token)}`),
  publicUpload: (token: string, form: FormData) =>
    request<{ status: string }>(`/api/public/scan/${encodeURIComponent(token)}`, { method: "POST", body: form }),
};
