"use client";

import { useMutation } from "@tanstack/react-query";
import { CircleAlert, CircleCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api/endpoints";
import { useT } from "@/lib/i18n";
import { AuthCard, authStyles } from "../../AuthCard";

export default function VerifyEmailPage() {
  const t = useT();
  const token = useParams<{ token: string }>().token;
  const verify = useMutation({ mutationFn: () => api.verifyEmail(token) });
  const { mutate } = verify;

  useEffect(() => {
    mutate();
  }, [mutate]);

  return (
    <AuthCard note={false}>
      <div className={authStyles.message} aria-live="polite">
        {verify.isPending || verify.isIdle ? (
          <>
            <div className="spinner" role="status" />
            <p>{t.verifyEmail.verifying}</p>
          </>
        ) : verify.isSuccess ? (
          <>
            <CircleCheck size={32} strokeWidth={1.5} className={authStyles.success} />
            <h1>{t.verifyEmail.doneTitle}</h1>
            <p>{verify.data.detail}</p>
          </>
        ) : (
          <>
            <CircleAlert size={32} strokeWidth={1.5} className={authStyles.failure} />
            <h1>{t.verifyEmail.failedTitle}</h1>
            <p>{verify.error?.message}</p>
          </>
        )}
        <Link href="/pessoas" className="button button-secondary">
          {t.verifyEmail.goToApp}
        </Link>
      </div>
    </AuthCard>
  );
}
