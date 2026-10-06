"use client";

import { keepPreviousData, useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import type { ListQuery, Page } from "./api/endpoints";

export const PAGE_SIZE = 50;
const REFRESH_MS = 10_000;

export function useUrlFilters<K extends string>(keys: readonly K[], ignoredForActive: readonly K[] = []) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const values = useMemo(() => {
    const result = {} as Record<K, string>;
    for (const key of keys) result[key] = params.get(key) ?? "";
    return result;
  }, [keys, params]);

  const update = useCallback(
    (key: K, value: string) => {
      const next = new URLSearchParams(params.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const clear = useCallback(() => router.replace(pathname, { scroll: false }), [pathname, router]);
  const active = keys.some((key) => !ignoredForActive.includes(key) && values[key]);
  return { values, update, clear, active };
}

export function usePagedList<T extends { id: number }>(name: string, load: (query: ListQuery) => Promise<Page<T>>, query: ListQuery) {
  const queryClient = useQueryClient();
  const cleaned = Object.fromEntries(Object.entries(query).filter(([, value]) => value !== "" && value !== undefined)) as ListQuery;
  const key = [name, cleaned] as const;
  const result = useInfiniteQuery({
    queryKey: key,
    queryFn: ({ pageParam }) => load({ ...cleaned, page: pageParam, page_size: PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (pages.length * PAGE_SIZE < last.total ? pages.length + 1 : undefined),
    placeholderData: keepPreviousData,
    refetchInterval: (state) => ((state.state.data?.pages.length ?? 1) <= 1 ? REFRESH_MS : false),
    refetchIntervalInBackground: false,
  });
  const items = useMemo(() => result.data?.pages.flatMap((page) => page.items) ?? [], [result.data]);
  const total = result.data?.pages[0]?.total ?? null;
  const remove = useCallback(
    (id: number) => queryClient.invalidateQueries({ queryKey: [name] }).then(() => id),
    [queryClient, name],
  );
  return {
    items,
    total,
    error: result.error instanceof Error ? result.error.message : null,
    loadingMore: result.isFetchingNextPage,
    hasMore: Boolean(result.hasNextPage),
    loadMore: () => {
      if (result.hasNextPage && !result.isFetchingNextPage) void result.fetchNextPage();
    },
    remove,
  };
}
