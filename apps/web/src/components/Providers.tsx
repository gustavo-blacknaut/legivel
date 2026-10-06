"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useState, type ReactNode } from "react";
import type { Instance } from "@/lib/api/endpoints";
import { LocaleProvider, isLanguage } from "@/lib/i18n";
import { ThemeProvider } from "./ThemeProvider";
import { ToastProvider } from "./Toast";

const InstanceContext = createContext<Instance | null>(null);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5_000, refetchOnWindowFocus: true, retry: (count, error) => count < 1 && !("status" in (error as object)) },
    },
  });
}

export function Providers({ instance, children }: { instance: Instance; children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  const language = isLanguage(instance.default_language) ? instance.default_language : "pt-BR";
  return (
    <InstanceContext.Provider value={instance}>
      <QueryClientProvider client={queryClient}>
        <LocaleProvider defaultLanguage={language} defaultTimeZone={instance.timezone}>
          <ThemeProvider>
            <ToastProvider>{children}</ToastProvider>
          </ThemeProvider>
        </LocaleProvider>
      </QueryClientProvider>
    </InstanceContext.Provider>
  );
}

export function useInstance(): Instance {
  const instance = useContext(InstanceContext);
  if (!instance) throw new Error("useInstance precisa estar dentro de Providers");
  return instance;
}
