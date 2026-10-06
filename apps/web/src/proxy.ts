import { NextResponse, type NextRequest } from "next/server";
import { NONCE_HEADER, contentSecurityPolicy, createNonce } from "@/lib/security-headers";

const PUBLIC_PREFIXES = ["/entrar", "/configuracao-inicial", "/convite/", "/verificar-email/", "/redefinir-senha", "/enviar/"];
const SESSION_COOKIES = ["legivel_session", "legivel_refresh"];
const POLICY_HEADER = "Content-Security-Policy";

function routeRequest(request: NextRequest, requestHeaders: Headers): NextResponse {
  const { pathname, search } = request.nextUrl;
  const isPublic = PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (isPublic || SESSION_COOKIES.some((name) => request.cookies.has(name))) {
    return NextResponse.next({ request: { headers: requestHeaders } });
  }
  const target = new URL("/entrar", request.url);
  if (pathname !== "/" && pathname !== "/pessoas") target.searchParams.set("next", pathname + search);
  return NextResponse.redirect(target);
}

export function proxy(request: NextRequest) {
  const nonce = createNonce();
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development");
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(NONCE_HEADER, nonce);
  requestHeaders.set(POLICY_HEADER, policy);
  const response = routeRequest(request, requestHeaders);
  response.headers.set(POLICY_HEADER, policy);
  return response;
}

export const config = {
  matcher: ["/((?!api|health|_next/static|_next/image|favicon.svg|.*\.(?:svg|png|webp|ico|txt)$).*)"],
};
