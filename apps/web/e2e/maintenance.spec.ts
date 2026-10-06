import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import path from "node:path";
import { ADMIN_STATE, READER_STATE, seedState } from "./support";

test.describe("proteção de dados e importação", () => {
  test.use({ storageState: ADMIN_STATE });

  test("histórico mostra alterações e desfaz a última revisão", async ({ page }) => {
    await page.goto(`/documentos/${seedState().document_id}`);
    const name = page.getByRole("textbox", { name: /^Nome completo/ });
    const original = await name.inputValue();
    await name.fill("REVISAO COM HISTORICO");
    await name.press("Control+Enter");
    await expect(page.getByText("Revisão salva.")).toBeVisible();
    await page.getByRole("button", { name: "Histórico de revisão" }).click();
    await expect(page.getByText("Depois: REVISAO COM HISTORICO")).toBeVisible();
    await page.getByRole("button", { name: "Desfazer última revisão" }).click();
    const dialog = page.getByRole("dialog", { name: "Desfazer revisão?" });
    await dialog.getByRole("button", { name: "Desfazer", exact: true }).click();
    await expect(name).toHaveValue(original);
    await expect(dialog).toBeHidden();
  });

  test("exportação seleciona documentos e baixa CSV e Excel", async ({ page }) => {
    await page.goto("/exportar");
    await expect(page.getByRole("checkbox").first()).toBeVisible();
    await page.getByRole("checkbox").first().check();
    for (const format of ["csv", "xlsx"]) {
      await page.getByRole("combobox", { name: /^Formato/ }).selectOption(format);
      const download = page.waitForEvent("download");
      await page.getByRole("button", { name: "Baixar selecionados" }).click();
      expect((await download).suggestedFilename()).toBe(`legivel-lote.${format}`);
    }
    await page.getByRole("button", { name: "Limpar seleção" }).click();
    await expect(page.getByRole("button", { name: "Baixar selecionados" })).toBeDisabled();
  });

  test("backup baixa, testa recuperação e permite cancelar restauração preparada", async ({ page }) => {
    await page.goto("/manutencao");
    await page.getByLabel("Senha do backup", { exact: true }).fill("senha-backup-browser-123");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Criar e baixar backup" }).click();
    const downloaded = await download;
    const file = await downloaded.path();
    expect(file).toBeTruthy();
    await page.getByLabel("Backup para conferir ou restaurar").setInputFiles(file!);
    await page.getByRole("button", { name: "Testar recuperação" }).click();
    await expect(page.getByText(/Recuperação testada em banco isolado/)).toBeVisible();
    await page.getByRole("button", { name: "Preparar restauração" }).click();
    const dialog = page.getByRole("dialog", { name: "Restaurar dados?" });
    await expect(dialog.getByRole("button", { name: "Confirmar", exact: true })).toBeDisabled();
    await dialog.getByLabel("Digite RESTAURAR").fill("RESTAURAR");
    await dialog.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect(page.getByRole("button", { name: "Cancelar restauração" })).toBeVisible();
    const paused = await page.request.post("/api/jobs", { headers: { "X-Requested-With": "legivel" } });
    expect(paused.status()).toBe(503);
    await page.getByRole("button", { name: "Cancelar restauração" }).click();
    await expect(page.getByRole("button", { name: "Cancelar restauração" })).toBeHidden();
    await expect(page.getByText("Restauração cancelada.")).toBeVisible();
  });

  test("PDF permite selecionar, girar, conferir e processar duas páginas", async ({ page }) => {
    await page.goto("/importar");
    await page.getByLabel("Arquivo PDF (até 100 MB)").setInputFiles(path.join(__dirname, "fixtures", "pdf-ficticio.pdf"));
    await page.getByRole("button", { name: "Ver páginas" }).click();
    await page.getByRole("checkbox", { name: "Página 3", exact: true }).uncheck();
    await page.getByRole("combobox", { name: /^Rotação 1/ }).selectOption("90");
    await page.getByRole("button", { name: "Prévia 1", exact: true }).click();
    await expect(page.getByRole("img", { name: "Prévia da página 1" })).toBeVisible();
    await page.getByRole("button", { name: "Enviar páginas para leitura" }).click();
    await expect(page).toHaveURL(/\/fila$/);
    const job = page.getByRole("article").filter({ hasText: "pdf-ficticio.pdf-pagina-1.jpg" }).first();
    await job.getByRole("link", { name: "Abrir", exact: true }).click({ timeout: 60_000 });
    await expect(page).toHaveURL(/\/registros\/\d+/);
    await expect(page.getByRole("heading", { name: "Dados lidos" })).toBeVisible();
  });

  test("novos painéis têm nomes acessíveis, contraste e navegação por teclado", async ({ page }) => {
    for (const route of ["/manutencao", "/exportar", "/importar"]) {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      for (const theme of ["light", "dark"]) {
        await page.locator("html").evaluate((element, value) => { element.setAttribute("data-theme", value); }, theme);
        const report = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        expect(report.violations.map((item) => ({ id: item.id, nodes: item.nodes.map((node) => node.target) })), `${route} ${theme}`).toEqual([]);
      }
    }
    await page.goto("/importar");
    await expect(page.getByRole("heading", { name: "Importar PDF", exact: true })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Ir para o conteúdo" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main")).toBeFocused();
  });
});

test.describe("acesso de consulta", () => {
  test.use({ storageState: READER_STATE });
  test("painéis protegidos não ficam disponíveis para leitores", async ({ page }) => {
    for (const route of ["/manutencao", "/exportar", "/importar"]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
    }
  });
});
