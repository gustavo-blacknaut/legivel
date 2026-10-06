"use client";

import { Suspense, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { SessionGate } from "@/lib/session";

const spinner = <div className="spinner spinner-page" role="status" aria-label="…" />;

export default function AuthenticatedLayout({ children }: { children: ReactNode }) {
  return (
    <SessionGate fallback={spinner}>
      <AppShell>
        <Suspense fallback={spinner}>{children}</Suspense>
      </AppShell>
    </SessionGate>
  );
}
