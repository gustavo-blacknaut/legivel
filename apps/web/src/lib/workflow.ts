import { ApiError, CSRF_HEADER, CSRF_VALUE, messageOf, refreshSession } from "./api/client";

export class DuplicateError extends Error {
  constructor(public documentId: number) { super("Este documento já foi enviado."); }
}
export async function workflowRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set(CSRF_HEADER, CSRF_VALUE);
  const options = { ...init, headers, credentials: "same-origin" as const };
  let response = await fetch(path, options);
  if (response.status === 401 && await refreshSession()) response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    if (response.status === 409 && payload?.detail?.document_id) throw new DuplicateError(payload.detail.document_id);
    throw new ApiError(response.status, messageOf(payload, "Não foi possível concluir a operação."));
  }
  return response;
}
export async function workflowJson<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await workflowRequest(path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  return response.status === 204 ? undefined as T : await response.json() as T;
}
export type ProcessingJob = { id: number; module: string; label: string; status: string; completed_pages: number; total_pages: number; result_id: number | null; error: string | null };
export async function enqueue(form: FormData): Promise<ProcessingJob> {
  return (await workflowRequest("/api/jobs", { method: "POST", body: form })).json();
}
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
