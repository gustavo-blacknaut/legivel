"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, type ReactNode } from "react";
import { ApiError, UNAUTHORIZED_EVENT } from "./api/client";
import { api, type User } from "./api/endpoints";
import { loginTarget } from "./redirect";

type SessionState = {
  user: User;
  can: (permission: string) => boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<unknown>;
};

const SessionContext = createContext<SessionState | null>(null);
export const ME_KEY = ["me"] as const;

export function SessionGate({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const me = useQuery({
    queryKey: ME_KEY,
    queryFn: api.me,
    retry: false,
    staleTime: 60_000,
  });

  const toLogin = useCallback(() => {
    queryClient.clear();
    router.replace(loginTarget(pathname));
  }, [queryClient, router, pathname]);

  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, toLogin);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, toLogin);
  }, [toLogin]);

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) toLogin();
  }, [me.error, toLogin]);

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    queryClient.clear();
    router.replace("/entrar");
  }, [queryClient, router]);

  if (!me.data) return <>{fallback}</>;
  const user = me.data;
  const value: SessionState = {
    user,
    can: (permission) => user.permissions.includes(permission),
    logout,
    refresh: me.refetch,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession precisa estar dentro de SessionGate");
  return context;
}
