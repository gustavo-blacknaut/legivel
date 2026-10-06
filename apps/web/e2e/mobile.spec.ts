import { expect, test } from "@playwright/test";
import path from "node:path";
import { ADMIN_STATE, horizontalOverflow, seedState } from "./support";

test.use({ storageState: ADMIN_STATE });
test("novas telas e comparação funcionam nas duas orientações", async ({ page }) => {
  for (const viewport of [{ width: 390, height: 844 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport);
    for (const route of ["/revisar", "/modelos", "/vencimentos"]) {
      await page.goto(route); await page.waitForLoadState("networkidle");
      expect((await horizontalOverflow(page)).overflow).toBeLessThanOrEqual(1);
    }
    await page.goto(`/documentos/${seedState().document_id}`);
    await page.getByRole("button", { name: "Comparar original e tratada" }).click();
    const dialog = page.getByRole("dialog", { name: "Comparação de imagens" });
    await expect.poll(() => dialog.getByRole("img").first().evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    expect((await horizontalOverflow(page)).overflow).toBeLessThanOrEqual(1);
    await dialog.getByRole("button", { name: "Fechar", exact: true }).click();
  }
});

test("captura nativa aceita arquivo, permite remover e mantém formulário utilizável", async ({ page }) => {
  await page.goto("/novo");
  await expect(page.locator("input[type=file][capture=environment]").first()).toHaveAttribute("accept", /image\/jpeg/);
  const file = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Frente: Escolher arquivo" }).click();
  await (await file).setFiles(path.join(__dirname, "fixtures", "rg-verso-ficticio.jpg"));
  await expect(page.getByRole("button", { name: "Remover", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Remover", exact: true }).click();
  await expect(page.getByRole("button", { name: "Frente: Escolher arquivo" })).toBeVisible();
});
