"use client";

import { BookOpen, CreditCard, Receipt, ScanLine, type LucideIcon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, type ModuleInfo } from "@/lib/api/endpoints";
import type { Messages } from "@/lib/i18n/pt-BR";

const ICONS: Record<string, LucideIcon> = { books: BookOpen, scanner: ScanLine, finance: Receipt, cards: CreditCard };

export function ModuleIcon({ module, size = 18 }: { module: string; size?: number }) {
  const Icon = ICONS[module] ?? ScanLine;
  return <Icon size={size} strokeWidth={1.75} aria-hidden="true" />;
}

export function moduleName(t: Messages, module: Pick<ModuleInfo, "key" | "name"> | string): string {
  const key = typeof module === "string" ? module : module.key;
  return t.modules.names[key] ?? (typeof module === "string" ? module : module.name);
}

export function useModules() {
  return useQuery({ queryKey: ["modules"], queryFn: api.modules, staleTime: Infinity });
}
