import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { ADMIN_STATE, WIDTHS, seedState } from "./support";

const OUTPUT = path.resolve(__dirname, "..", "..", "..", "docs", "screenshots");
const FRAMES = path.join(OUTPUT, "frames");
const SAMPLE = path.join(__dirname, "fixtures", "rg-verso-ficticio.jpg");

test.skip(!process.env.SCREENSHOTS, "defina SCREENSHOTS=1 para gerar as capturas");
test.use({ storageState: ADMIN_STATE });

async function settle(page: Page, route: string) {
  await page.goto(route);
  await page.waitForLoadState("networkidle");
  await expect(page.locator("h1").first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

async function capture(page: Page, folder: string, name: string, fullPage = false) {
  mkdirSync(folder, { recursive: true });
  await page.screenshot({ path: path.join(folder, `${name}.png`), fullPage, animations: "disabled" });
}

for (const width of WIDTHS) {
  test(`telas principais em ${width}px`, async ({ page, browser }) => {
    const state = seedState();
    const height = width < 768 ? 812 : width < 1280 ? 1024 : 900;
    await page.setViewportSize({ width, height });
    const folder = path.join(OUTPUT, String(width));
    const screens: [string, string][] = [
      ["pessoas", "/pessoas"],
      ["pessoa", `/pessoas/${state.person_id}`],
      ["documentos", "/documentos"],
      ["revisao", `/documentos/${state.document_id}`],
      ["novo-documento", "/novo"],
      ["registros", "/registros"],
      ["registro", `/registros/${state.record_id}`],
      ["cartao", `/registros/${state.card_record_id}`],
      ["leitura", "/leitura"],
      ["busca", "/busca?q=cooperativa"],
      ["auditoria", "/auditoria"],
      ["conta", "/conta"],
      ["usuarios", "/usuarios"],
      ["configuracoes", "/configuracoes"],
    ];
    for (const [name, route] of screens) {
      await settle(page, route);
      await capture(page, folder, name);
    }
    await settle(page, "/pessoas");
    await page.getByRole("button", { name: /^Apagar / }).first().click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await capture(page, folder, "apagar");
    if (width < 861) {
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Abrir menu" }).click();
      await page.waitForTimeout(300);
      await capture(page, folder, "menu");
    }
    const anonymous = await browser.newContext({ viewport: { width, height }, storageState: { cookies: [], origins: [] } });
    const guest = await anonymous.newPage();
    await settle(guest, "/entrar");
    await capture(guest, folder, "entrar");
    await settle(guest, `/enviar/${state.scan_token}`);
    await capture(guest, folder, "envio-remoto");
    await anonymous.close();
  });
}

test("tema escuro", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await settle(page, `/documentos/${seedState().document_id}`);
  await capture(page, path.join(OUTPUT, "1280"), "revisao-escuro");
  await settle(page, "/pessoas");
  await capture(page, path.join(OUTPUT, "1280"), "pessoas-escuro");
  await settle(page, `/registros/${seedState().record_id}`);
  await capture(page, path.join(OUTPUT, "1280"), "registro-escuro");
});

test("quadros do fluxo principal", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  let index = 0;
  const frame = async () => capture(page, FRAMES, String(index++).padStart(2, "0"));
  await settle(page, "/pessoas");
  await frame();
  await settle(page, "/novo");
  await frame();
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByRole("button", { name: "Verso: Escolher arquivo" }).click()]);
  await chooser.setFiles({ name: "verso.jpg", mimeType: "image/jpeg", buffer: readFileSync(SAMPLE) });
  await frame();
  await page.getByRole("button", { name: "Extrair dados" }).click();
  await page.waitForTimeout(300);
  await frame();
  await expect(page).toHaveURL(/\/documentos\/\d+/, { timeout: 60_000 });
  await page.waitForLoadState("networkidle");
  await frame();
  await page.getByRole("button", { name: "Confirmar revisão" }).click();
  await expect(page.getByText("Revisão salva.")).toBeVisible();
  await frame();
  await page.getByRole("link", { name: "Voltar para a pessoa" }).click();
  await page.waitForLoadState("networkidle");
  await frame();
});
