import { describe, expect, it } from "vitest";
import { confidenceLevel, createFormatter, describeDevice, formatCpf, initials, normalizeForMatch } from "./format";

describe("formatação", () => {
  it("formata CPF somente com 11 dígitos", () => {
    expect(formatCpf("52998224725")).toBe("529.982.247-25");
    expect(formatCpf("123")).toBe("123");
    expect(formatCpf(null)).toBe("");
  });

  it("classifica a confiança do OCR", () => {
    expect(confidenceLevel(0.95)).toBe("high");
    expect(confidenceLevel(0.8)).toBe("medium");
    expect(confidenceLevel(0.2)).toBe("low");
    expect(confidenceLevel(null)).toBe("unknown");
  });

  it("gera iniciais", () => {
    expect(initials("maria da silva")).toBe("MS");
    expect(initials("")).toBe("?");
  });

  it("compara nomes sem acento, pontuação e caixa", () => {
    expect(normalizeForMatch("João  Ávila")).toBe(normalizeForMatch("JOAO AVILA"));
    expect(normalizeForMatch("529.982.247-25")).toBe("52998224725");
  });

  it("usa o fuso configurado", () => {
    const format = createFormatter("pt-BR", "America/Manaus");
    expect(format.dateTime("2026-01-10T12:00:00Z")).toContain("08:00");
    expect(createFormatter("pt-BR", "America/Sao_Paulo").date("2026-01-10T01:00:00Z")).toBe("09/01/2026");
  });

  it("descreve o aparelho da sessão", () => {
    expect(describeDevice("Mozilla/5.0 (Linux; Android 14) Chrome/130", "?")).toBe("Chrome · Android");
    expect(describeDevice(null, "Desconhecido")).toBe("Desconhecido");
  });
});
