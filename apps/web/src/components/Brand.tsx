"use client";

import { useInstance } from "./Providers";

type BrandProps = { className?: string; nameClassName?: string; size?: number };

export function Brand({ className, nameClassName, size = 28 }: BrandProps) {
  const instance = useInstance();
  return (
    <span className={className}>
      <img src={instance.logo_url ?? "/favicon.svg"} alt="" width={size} height={size} />
      <span className={nameClassName}>{instance.name}</span>
    </span>
  );
}
