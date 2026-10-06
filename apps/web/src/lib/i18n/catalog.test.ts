import { describe, expect, it } from "vitest";
import { en } from "./en";
import { ptBR } from "./pt-BR";

function shape(value: unknown, prefix = ""): string[] {
  if (typeof value === "function") return [`${prefix}()`];
  if (Array.isArray(value)) return [`${prefix}[${value.length}]`];
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([key, child]) => shape(child, prefix ? `${prefix}.${key}` : key));
  }
  return [prefix];
}

describe("catálogos de idioma", () => {
  it("inglês tem exatamente as mesmas chaves que português", () => {
    expect(shape(en).sort()).toEqual(shape(ptBR).sort());
  });

  it("nenhum texto ficou vazio", () => {
    const strings = (value: unknown): string[] =>
      typeof value === "string" ? [value] : value && typeof value === "object" ? Object.values(value).flatMap(strings) : [];
    for (const catalog of [ptBR, en]) {
      expect(strings(catalog).filter((text) => text.trim() === "")).toEqual([]);
    }
  });
});
