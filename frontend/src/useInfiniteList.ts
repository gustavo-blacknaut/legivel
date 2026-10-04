import { useCallback, useEffect, useRef, useState } from "react";
import type { PageResult } from "./types";

const PAGE_SIZE = 50;
const REFRESH_INTERVAL_MS = 10_000;

export function useInfiniteList<T extends { id: number }>(
  load: (params: URLSearchParams) => Promise<PageResult<T>>,
  filters: URLSearchParams,
) {
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageRef = useRef(0);
  const requestRef = useRef(0);
  const loadRef = useRef(load);
  loadRef.current = load;
  const filterKey = filters.toString();

  const fetchPage = useCallback(
    async (page: number, replace: boolean) => {
      const requestId = ++requestRef.current;
      const params = new URLSearchParams(filterKey);
      params.set("page", String(page));
      params.set("page_size", String(PAGE_SIZE));
      setLoading(true);
      try {
        const result = await loadRef.current(params);
        if (requestId !== requestRef.current) return;
        pageRef.current = page;
        setTotal(result.total);
        setItems((current) => (replace ? result.items : [...current, ...result.items]));
        setError(null);
      } catch (caught) {
        if (requestId === requestRef.current) setError(caught instanceof Error ? caught.message : "Falha ao carregar");
      } finally {
        if (requestId === requestRef.current) setLoading(false);
      }
    },
    [filterKey],
  );

  const reload = useCallback(() => fetchPage(1, true), [fetchPage]);

  useEffect(() => {
    setItems([]);
    setTotal(null);
    reload();
  }, [reload]);

  const hasMore = total !== null && items.length < total;

  const loadMore = useCallback(() => {
    if (!loading && hasMore) fetchPage(pageRef.current + 1, false);
  }, [fetchPage, hasMore, loading]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible" && pageRef.current <= 1) reload();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [reload]);

  const remove = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
    setTotal((current) => (current === null ? current : current - 1));
  }, []);

  return { items, total, loading, error, hasMore, loadMore, reload, remove };
}

export function useSentinel(onVisible: () => void, enabled: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const callbackRef = useRef(onVisible);
  callbackRef.current = onVisible;

  useEffect(() => {
    const element = ref.current;
    if (!element || !enabled) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) callbackRef.current();
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [enabled]);

  return ref;
}
