import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { ADMIN_STATE, READER_STATE, seedState } from "./support";

const sample = { name: "modelo.jpg", mimeType: "image/jpeg", buffer: readFileSync(path.join(__dirname, "fixtures", "rg-verso-ficticio.jpg")) };
async function createItem(page: Page, module: "documents" | "scanner") {
  const response = await page.request.post("/api/jobs", { headers: { "X-Requested-With": "legivel" }, multipart: module === "documents" ? { front: sample, duplicate: "keep" } : { module, pages: sample } });
  expect(response.status()).toBe(202);
  const job = await response.json();
  let id = 0;
  await expect.poll(async () => {
    const jobs = await (await page.request.get("/api/jobs")).json();
    const current = jobs.find((item: { id: number }) => item.id === job.id);
    id = current?.result_id ?? 0;
    return current?.status;
  }, { timeout: 60_000 }).toBe("completed");
  return id;
}

test.describe("revisão e modelos", () => {
  test.use({ storageState: ADMIN_STATE });

  test("compara original e tratada com ampliação e retorno de foco", async ({ page }) => {
    await page.goto(`/documentos/${seedState().document_id}`);
    const trigger = page.getByRole("button", { name: "Comparar original e tratada" });
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Comparação de imagens" });
    await expect(dialog.getByRole("img")).toHaveCount(2);
    await expect.poll(() => dialog.getByRole("img").first().evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    await expect.poll(() => dialog.getByRole("img").last().evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    await dialog.getByRole("combobox", { name: /^Ampliação/ }).selectOption("2");
    await expect(dialog.getByRole("img").first()).toHaveAttribute("style", "width: 200%;");
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("cria modelo, aplica campos, alerta validade e preserva dados ao excluir", async ({ page }) => {
    const name = `Contrato ${Date.now()}`;
    await page.goto("/modelos");
    await page.getByRole("button", { name: "Novo modelo" }).click();
    const dialog = page.getByRole("dialog", { name: "Novo modelo" });
    await dialog.getByLabel("Nome do modelo", { exact: true }).fill(name);
    await dialog.getByLabel("Nome do campo", { exact: true }).fill("Cliente do contrato");
    await dialog.getByLabel("Obrigatório", { exact: true }).check();
    await dialog.getByRole("button", { name: "Adicionar campo" }).click();
    const field = dialog.getByRole("group", { name: "Campo 2", exact: true });
    await field.getByLabel("Nome do campo", { exact: true }).fill("Validade do contrato");
    await field.getByRole("combobox", { name: /^Formato do campo/ }).selectOption("date");
    await field.getByLabel("Usar nos alertas de vencimento").check();
    await dialog.getByRole("button", { name: "Salvar modelo" }).click();
    await expect(dialog).toBeHidden();
    const id = await createItem(page, "scanner");
    await page.goto(`/registros/${id}`);
    await page.getByRole("combobox", { name: /^Escolher modelo/ }).selectOption({ label: name });
    await page.getByRole("button", { name: "Aplicar modelo" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Aplicar", exact: true }).click();
    await expect(page.getByText(`Modelo aplicado: ${name}`)).toBeVisible();
    await page.getByRole("textbox", { name: /^Cliente do contrato/ }).fill("CLIENTE DE TESTE");
    const alerts = await (await page.request.get("/api/expirations")).json();
    await page.getByLabel("Validade do contrato", { exact: true }).fill(alerts.today);
    const reviewed = page.waitForResponse((response) => response.url().includes(`/api/records/${id}`) && response.request().method() === "PUT" && response.status() === 200);
    await page.getByRole("button", { name: "Confirmar revisão", exact: true }).click();
    await reviewed;
    await page.goto("/vencimentos");
    await expect(page.locator("article").filter({ has: page.locator(`a[href='/registros/${id}']`) })).toContainText("Vence hoje");
    await page.getByRole("combobox", { name: /^Avisar com antecedência/ }).selectOption("7");
    await expect.poll(async () => (await (await page.request.get("/api/expirations")).json()).days).toBe(7);
    await page.goto("/modelos");
    await page.locator("article").filter({ has: page.getByRole("heading", { name, exact: true }) }).getByRole("button", { name: "Excluir modelo" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Excluir", exact: true }).click();
    await page.goto(`/registros/${id}`);
    await expect(page.getByRole("textbox", { name: /^Cliente do contrato/ })).toHaveValue("CLIENTE DE TESTE");
  });

  test("lote misto confirma alterações, protege ao pular e termina sem voltar à lista", async ({ page }) => {
    await page.goto("/revisar");
    const doc = await createItem(page, "documents");
    const record = await createItem(page, "scanner");
    await page.reload();
    await page.getByRole("checkbox", { name: new RegExp(`Identidade #${doc} ·`) }).check();
    await page.getByRole("checkbox", { name: new RegExp(`Leitura #${record} ·`) }).check();
    await page.getByRole("button", { name: "Iniciar revisão (2)", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/documentos/${doc}\\?batch=`));
    await page.getByRole("textbox", { name: /^Nome completo/ }).fill("NOME REVISADO EM LOTE");
    await page.getByRole("button", { name: "Pular este item" }).click();
    const dialog = page.getByRole("dialog", { name: "Descartar alterações não salvas?" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Continuar revisando" }).click();
    await page.getByRole("button", { name: "Salvar e próximo" }).click();
    await expect(page).toHaveURL(new RegExp(`/registros/${record}\\?batch=`));
    await page.getByRole("textbox", { name: /^Título/ }).fill("LEITURA REVISADA EM LOTE");
    await page.getByRole("button", { name: "Salvar e próximo" }).click();
    await expect(page).toHaveURL(/\/revisar\?finished=2&total=2/);
    await expect(page.getByText(/Lote encerrado: 2 de 2/)).toBeVisible();
    expect((await (await page.request.get(`/api/documents/${doc}`)).json()).status).toBe("reviewed");
    expect((await (await page.request.get(`/api/records/${record}`)).json()).status).toBe("reviewed");
  });

  for (const theme of ["light", "dark"]) {
    test(`novas telas passam nas regras de acessibilidade em ${theme}`, async ({ page }) => {
      await page.addInitScript((value) => localStorage.setItem("legivel:theme", value), theme);
      for (const route of ["/revisar", "/modelos", "/vencimentos"]) {
        await page.goto(route); await page.waitForLoadState("networkidle");
        expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
      }
    });
  }
});

test.describe("permissões de produtividade", () => {
  test.use({ storageState: READER_STATE });
  test("leitor consulta vencimentos e modelos sem acesso a originais ou edição", async ({ page }) => {
    await page.goto(`/documentos/${seedState().document_id}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Comparar original e tratada" })).toHaveCount(0);
    await page.goto("/modelos");
    await expect(page.getByRole("button", { name: "Novo modelo" })).toHaveCount(0);
    await page.goto("/revisar");
    await expect(page.getByRole("button", { name: /Iniciar revisão/ })).toHaveCount(0);
    expect((await page.request.get("/api/review/queue")).status()).toBe(403);
  });
});
