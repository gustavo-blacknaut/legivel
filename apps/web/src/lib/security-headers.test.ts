import { describe, expect, it } from "vitest";
import { contentSecurityPolicy, createNonce } from "./security-headers";

describe("contentSecurityPolicy", () => {
  it("allows scripts only through the nonce", () => {
    const policy = contentSecurityPolicy("abc123", false);
    expect(policy).toContain("script-src 'self' 'nonce-abc123' 'strict-dynamic'");
    expect(policy).not.toMatch(/script-src[^;]*'unsafe-inline'/);
    expect(policy).not.toContain("'unsafe-eval'");
  });

  it("allows eval only in development", () => {
    expect(contentSecurityPolicy("abc123", true)).toContain("'unsafe-eval'");
  });
});

describe("createNonce", () => {
  it("creates a different base64 value each time", () => {
    const first = createNonce();
    expect(first).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    expect(createNonce()).not.toBe(first);
  });
});
