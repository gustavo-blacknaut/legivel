import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, UNAUTHORIZED_EVENT, client, messageOf, unwrap } from "./client";

function respond(status: number, body: unknown = {}) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cliente da API", () => {
  it("envia o cabeçalho de CSRF", async () => {
    const fetcher = vi.fn<typeof fetch>(async () => respond(200, { required: false }));
    vi.stubGlobal("fetch", fetcher);
    await client.GET("/api/setup", { fetch: fetcher });
    const request = fetcher.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("X-Requested-With")).toBe("legivel");
  });

  it("renova a sessão uma vez e repete a requisição", async () => {
    const calls: string[] = [];
    const fetcher = vi.fn<typeof fetch>(async (input) => {
      const url = input instanceof Request ? input.url : String(input);
      calls.push(new URL(url, "http://localhost").pathname);
      if (url.endsWith("/api/auth/refresh")) return respond(200, {});
      return calls.filter((item) => item === "/api/people").length === 1 ? respond(401, { detail: "Não autenticado" }) : respond(200, { items: [], total: 0 });
    });
    vi.stubGlobal("fetch", fetcher);
    const data = await unwrap(client.GET("/api/people", { params: { query: {} } }));
    expect(data).toEqual({ items: [], total: 0 });
    expect(calls).toEqual(["/api/people", "/api/auth/refresh", "/api/people"]);
  });

  it("avisa quando a sessão não pode ser renovada", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => respond(401, { detail: "Não autenticado" })));
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);
    await expect(unwrap(client.GET("/api/people", { params: { query: {} } }))).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("extrai a mensagem de erro da API", () => {
    expect(messageOf({ detail: "E-mail ou senha inválidos." }, "x")).toBe("E-mail ou senha inválidos.");
    expect(messageOf({ detail: [{ msg: "campo obrigatório" }] }, "x")).toBe("campo obrigatório");
    expect(messageOf(null, "padrão")).toBe("padrão");
  });
});
