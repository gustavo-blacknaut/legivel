import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export const CSRF_HEADER = "X-Requested-With";
export const CSRF_VALUE = "legivel";
export const UNAUTHORIZED_EVENT = "legivel:unauthorized";
const NO_RETRY_PREFIXES = ["/api/auth/login", "/api/auth/refresh", "/api/auth/logout", "/api/public/", "/api/setup"];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let refreshing: Promise<boolean> | null = null;

export function refreshSession(fetcher: typeof fetch = fetch): Promise<boolean> {
  refreshing ??= fetcher("/api/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { [CSRF_HEADER]: CSRF_VALUE },
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

function pathOf(url: string): string {
  return new URL(url, "http://localhost").pathname;
}

const retained = new WeakMap<Request, Request>();

const sessionMiddleware: Middleware = {
  async onRequest({ request }) {
    request.headers.set(CSRF_HEADER, CSRF_VALUE);
    retained.set(request, request.clone());
    return request;
  },
  async onResponse({ request, response }) {
    const path = pathOf(request.url);
    if (response.status !== 401 || NO_RETRY_PREFIXES.some((prefix) => path.startsWith(prefix))) {
      return response;
    }
    const copy = retained.get(request);
    if (copy && (await refreshSession())) {
      const retried = await fetch(copy);
      if (retried.status !== 401) return retried;
    }
    if (path !== "/api/auth/me" && typeof window !== "undefined") {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    return response;
  },
};

export const client = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  credentials: "same-origin",
  fetch: (request) => globalThis.fetch(request),
});
client.use(sessionMiddleware);

export function messageOf(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string") return first.msg;
    }
  }
  return fallback;
}

type Result<T> = { data?: T; error?: unknown; response: Response };

export async function unwrap<T>(promise: Promise<Result<T>>, fallback = "Algo deu errado. Tente novamente."): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw new ApiError(response.status, messageOf(error, fallback));
  return data as T;
}

export async function sendForm<T>(path: string, form: FormData, method: "POST" | "PUT" = "POST"): Promise<T> {
  const init = (): RequestInit => ({ method, body: form, credentials: "same-origin", headers: { [CSRF_HEADER]: CSRF_VALUE } });
  let response = await fetch(path, init());
  if (response.status === 401 && !NO_RETRY_PREFIXES.some((prefix) => path.startsWith(prefix)) && (await refreshSession())) {
    response = await fetch(path, init());
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, messageOf(payload, "Não foi possível enviar."));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
