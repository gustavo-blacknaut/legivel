import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./PageHead.module.css";

type PageHeadProps = { title: string; description?: ReactNode; actions?: ReactNode; back?: { href: string; label: string } };

export function PageHead({ title, description, actions, back }: PageHeadProps) {
  return (
    <div className={styles.head}>
      <div className={styles.text}>
        {back && (
          <Link href={back.href} className={styles.back}>
            <ArrowLeft size={14} />
            {back.label}
          </Link>
        )}
        <h1>{title}</h1>
        {description && <div className={styles.description}>{description}</div>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
}
