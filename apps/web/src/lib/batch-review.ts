"use client";
import { useMemo, useSyncExternalStore } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export type ReviewItem = { entity: "document" | "record"; id: number; title?: string; created_at?: string };
type Batch = { items: ReviewItem[]; done: string[] };
const prefix = "legivel:review-batch:";
const eventName = "legivel:review-batch-changed";
const subscribe = (callback: () => void) => { window.addEventListener(eventName, callback); return () => window.removeEventListener(eventName, callback); };
const keyOf = (item: ReviewItem) => `${item.entity}:${item.id}`;
export const reviewHref = (item: ReviewItem, token: string) => `/${item.entity === "document" ? "documentos" : "registros"}/${item.id}?batch=${token}`;
export function startBatch(items: ReviewItem[]): string {
  const first = items[0];
  if (!first) throw new Error("Selecione ao menos um item.");
  const token = crypto.randomUUID();
  // Only identifiers are kept in the browser, never names or extracted fields.
  sessionStorage.setItem(prefix + token, JSON.stringify({ items: items.map(({ entity, id }) => ({ entity, id })), done: [] }));
  return reviewHref(first, token);
}

export function useBatchReview(entity: ReviewItem["entity"], id: number) {
  const token = useSearchParams().get("batch") ?? "";
  const router = useRouter();
  const raw = useSyncExternalStore(subscribe, () => { try { return sessionStorage.getItem(prefix + token); } catch { return null; } }, () => null);
  const batch = useMemo(() => {
    try {
      const value = JSON.parse(raw ?? "null") as Batch | null;
      return value && Array.isArray(value.items) && value.items.length <= 200 && Array.isArray(value.done) && value.items.every((item) => item && ["document", "record"].includes(item.entity) && Number.isSafeInteger(item.id) && item.id > 0) ? value : null;
    } catch { return null; }
  }, [raw]);
  const index = batch?.items.findIndex((item) => item.entity === entity && item.id === id) ?? -1;
  const navigate = (offset: number, saved = false) => {
    if (!batch || index < 0) return;
    const done = saved ? [...new Set([...batch.done, keyOf({ entity, id })])] : batch.done;
    const next = { ...batch, done };
    sessionStorage.setItem(prefix + token, JSON.stringify(next));
    window.dispatchEvent(new Event(eventName));
    const target = batch.items[index + offset];
    if (target) router.push(reviewHref(target, token));
    else router.push(`/revisar?finished=${done.length}&total=${batch.items.length}`);
  };
  return { active: index >= 0, index, total: batch?.items.length ?? 0, done: batch?.done.length ?? 0, navigate };
}
