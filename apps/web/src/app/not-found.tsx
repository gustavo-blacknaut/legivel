"use client";

import { MapPinOff } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/ListState";
import { useT } from "@/lib/i18n";

export default function NotFound() {
  const t = useT();
  return (
    <main>
      <EmptyState
        icon={MapPinOff}
        title={t.notFound.title}
        text={t.notFound.text}
        action={
          <Link href="/pessoas" className="button button-secondary">
            {t.notFound.action}
          </Link>
        }
      />
    </main>
  );
}
