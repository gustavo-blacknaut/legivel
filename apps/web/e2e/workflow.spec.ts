import { expect, test } from "@playwright/test";
import { ADMIN_STATE, seedState } from "./support";

test.describe("organização e ocultação", () => {
  test.use({ storageState: ADMIN_STATE });
  test("salva pasta, etiquetas e busca", async ({ page }) => {
    await page.goto(`/documentos/${seedState().document_id}`);
    await page.getByLabel("Pasta", { exact: true }).fill("Clientes de teste");
    await page.getByLabel("Etiquetas (separadas por vírgula)").fill("mensal, conferido");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(page.getByText("Salvo", { exact: true })).toBeVisible();
    await page.goto("/organizar");
    await page.getByRole("combobox", { name: "Pasta", exact: true }).selectOption("Clientes de teste");
    await expect(page).toHaveURL(/folder=Clientes/);
    await expect(page.getByText("Clientes de teste · conferido, mensal")).toBeVisible();
    await page.getByText("Buscas salvas", { exact: true }).click();
    await page.getByLabel("Nome da busca").fill("Clientes mensais");
    await page.getByRole("button", { name: "Salvar busca atual" }).click();
    await expect(page.getByRole("link", { name: "Clientes mensais" })).toBeVisible();
    await page.reload();
    await page.getByText("Buscas salvas", { exact: true }).click();
    await expect(page.getByRole("link", { name: "Clientes mensais" })).toBeVisible();
  });

  test("mostra recorte, confere prévia e baixa PDF ocultado", async ({ page }) => {
    await page.goto(`/documentos/${seedState().document_id}`);
    await page.getByRole("button", { name: "Próximo campo a conferir" }).click();
    await expect(page.getByText(/Trecho do campo:/)).toBeVisible();
    await page.getByRole("textbox", { name: /^Nome completo/ }).focus();
    await expect(page.locator("canvas[role=img]")).toBeVisible();
    await expect.poll(() => page.locator("canvas[role=img]").evaluate((node) => (node as HTMLCanvasElement).width)).toBeGreaterThan(1);
    await page.getByRole("textbox", { name: /^Nome completo/ }).fill("MARIANA REVISAO POR TECLADO");
    await page.keyboard.press("Control+Enter");
    await expect(page.getByText("Revisão salva.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Exportar com ocultação" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("button", { name: "Baixar PDF" })).toBeDisabled();
    await dialog.getByText("Área (%)", { exact: true }).click();
    await dialog.getByRole("button", { name: "Salvar", exact: true }).click();
    const pages = await dialog.getByRole("combobox").locator("option").all();
    for (const option of pages) {
      await dialog.getByRole("combobox").selectOption(await option.getAttribute("value") ?? "");
      const response = page.waitForResponse((item) => item.url().includes("/api/redaction/") && item.status() === 200);
      await dialog.getByRole("button", { name: "Conferir prévia" }).click();
      await response;
      await expect(dialog.getByRole("button", { name: "Selecionar áreas" })).toBeVisible();
    }
    await dialog.evaluate((element) => { element.scrollTop = 0; });
    await page.screenshot({ path: "test-results/ocultacao.png" });
    const [download] = await Promise.all([page.waitForEvent("download"), dialog.getByRole("button", { name: "Baixar PDF" }).click()]);
    expect(download.suggestedFilename()).toMatch(/ocultado\.pdf$/);
  });
});
