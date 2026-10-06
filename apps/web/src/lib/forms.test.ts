import { describe, expect, it } from "vitest";
import { z } from "zod";
import { codeField, emailField, newPasswordSchema, optionalCpf, optionalDate, validate } from "./forms";
import { ptBR } from "./i18n/pt-BR";

const t = ptBR;

describe("validação dos formulários", () => {
  it("exige senha forte e confirmação igual", () => {
    const schema = newPasswordSchema(t, 10, true);
    expect(validate(schema, { password: "curta1", confirm: "curta1" })).toMatchObject({ ok: false, errors: { password: t.validation.passwordShort(10) } });
    expect(validate(schema, { password: "somenteletras", confirm: "somenteletras" })).toMatchObject({ ok: false, errors: { password: t.validation.passwordMixed } });
    expect(validate(schema, { password: "senha-forte-1", confirm: "outra" })).toMatchObject({ ok: false, errors: { confirm: t.validation.passwordMismatch } });
    expect(validate(schema, { password: "senha-forte-1", confirm: "senha-forte-1" }).ok).toBe(true);
  });

  it("valida e-mail", () => {
    const schema = z.object({ email: emailField(t) });
    expect(validate(schema, { email: "sem-arroba" }).ok).toBe(false);
    expect(validate(schema, { email: " ana@exemplo.com.br " })).toEqual({ ok: true, data: { email: "ana@exemplo.com.br" } });
  });

  it("aceita CPF e data vazios ou no formato", () => {
    const schema = z.object({ cpf: optionalCpf(t), birth: optionalDate(t) });
    expect(validate(schema, { cpf: "", birth: "" }).ok).toBe(true);
    expect(validate(schema, { cpf: "529.982.247-25", birth: "01/02/1990" }).ok).toBe(true);
    expect(validate(schema, { cpf: "529", birth: "1990-02-01" })).toMatchObject({ ok: false, errors: { cpf: t.validation.cpf, birth: t.validation.date } });
  });

  it("aceita código TOTP ou de recuperação", () => {
    const schema = z.object({ code: codeField(t) });
    expect(validate(schema, { code: "123 456" }).ok).toBe(true);
    expect(validate(schema, { code: "a1b2c-3d4e5" }).ok).toBe(true);
    expect(validate(schema, { code: "12345" }).ok).toBe(false);
  });
});
