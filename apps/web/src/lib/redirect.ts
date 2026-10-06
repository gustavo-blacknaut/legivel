const FALLBACK = "/pessoas";

export function safeReturnPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return FALLBACK;
  try {
    const parsed = new URL(value, "http://legivel.invalid");
    if (parsed.origin !== "http://legivel.invalid") return FALLBACK;
    if (parsed.pathname.startsWith("/api/") || parsed.pathname === "/entrar") return FALLBACK;
    return parsed.pathname + parsed.search;
  } catch {
    return FALLBACK;
  }
}

export function loginTarget(pathname: string | null): string {
  if (!pathname || pathname === "/" || pathname === FALLBACK) return "/entrar";
  return `/entrar?next=${encodeURIComponent(pathname)}`;
}
