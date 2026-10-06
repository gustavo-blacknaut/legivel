"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { useT } from "@/lib/i18n";
import { EmptyState } from "./ListState";
import page from "./Page.module.css";

export function Forbidden() {
  const t = useT();
  return (
    <div className={page.page}>
      <EmptyState
        icon={Lock}
        title={t.common.forbiddenTitle}
        text={t.common.forbiddenText}
        action={
          <Link href="/pessoas" className="button button-secondary">
            {t.nav.people}
          </Link>
        }
      />
    </div>
  );
}
