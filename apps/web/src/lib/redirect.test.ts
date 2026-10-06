import { describe, expect, it } from "vitest";
import { loginTarget, safeReturnPath } from "./redirect";

describe("safeReturnPath", () => {
  it.each([
    ["/documentos/5", "/documentos/5"],
    ["/pessoas?status=reviewed", "/pessoas?status=reviewed"],
    ["//exemplo.invalid/roubo", "/pessoas"],
    ["/\\exemplo.invalid", "/pessoas"],
    ["https://exemplo.invalid", "/pessoas"],
    ["javascript:alert(1)", "/pessoas"],
    ["/api/auth/logout", "/pessoas"],
    ["/entrar", "/pessoas"],
    [null, "/pessoas"],
    ["", "/pessoas"],
  ])("%s vira %s", (input, expected) => {
    expect(safeReturnPath(input)).toBe(expected);
  });
});

describe("loginTarget", () => {
  it("guarda a rota de origem", () => {
    expect(loginTarget("/auditoria")).toBe("/entrar?next=%2Fauditoria");
    expect(loginTarget("/pessoas")).toBe("/entrar");
    expect(loginTarget(null)).toBe("/entrar");
  });
});
