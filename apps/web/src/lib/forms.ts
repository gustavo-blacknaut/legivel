import { z } from "zod";
import type { Messages } from "./i18n/pt-BR";

export type FieldErrors = Record<string, string>;
export type Validation<T> = { ok: true; data: T } | { ok: false; errors: FieldErrors };

export function validate<T>(schema: z.ZodType<T>, values: unknown): Validation<T> {
  const parsed = schema.safeParse(values);
  if (parsed.success) return { ok: true, data: parsed.data };
  const errors: FieldErrors = {};
  for (const issue of parsed.error.issues) {
    const key = issue.path.join(".") || "form";
    errors[key] ??= issue.message;
  }
  return { ok: false, errors };
}

const CPF_PATTERN = /^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$/;
const DATE_PATTERN = /^\d{2}\/\d{2}\/\d{4}$/;

export function emailField(t: Messages) {
  return z.string().trim().min(1, t.validation.required).max(254, t.validation.tooLong(254)).email(t.validation.email);
}

export function passwordField(t: Messages, minimum: number, mixed: boolean) {
  return z
    .string()
    .min(minimum, t.validation.passwordShort(minimum))
    .max(256, t.validation.tooLong(256))
    .refine((value) => !mixed || (/[A-Za-zÀ-ÿ]/.test(value) && /[^A-Za-zÀ-ÿ]/.test(value)), t.validation.passwordMixed);
}

export function newPasswordSchema(t: Messages, minimum: number, mixed: boolean) {
  return z
    .object({ password: passwordField(t, minimum, mixed), confirm: z.string() })
    .refine((value) => value.password === value.confirm, { message: t.validation.passwordMismatch, path: ["confirm"] });
}

export function requiredText(t: Messages, max = 120) {
  return z.string().trim().min(1, t.validation.required).max(max, t.validation.tooLong(max));
}

export function optionalCpf(t: Messages) {
  return z.string().trim().refine((value) => value === "" || CPF_PATTERN.test(value), t.validation.cpf);
}

export function optionalDate(t: Messages) {
  return z.string().trim().refine((value) => value === "" || DATE_PATTERN.test(value), t.validation.date);
}

export function codeField(t: Messages) {
  return z
    .string()
    .trim()
    .refine((value) => /^\d{6}$/.test(value.replace(/\s/g, "")) || /^[0-9a-f]{5}-?[0-9a-f]{5}$/i.test(value), t.validation.code);
}

export const PASSWORD_DEFAULTS = { minimum: 10, mixed: true };
