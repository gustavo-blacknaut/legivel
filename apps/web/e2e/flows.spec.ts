import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { ADMIN_STATE, READER_STATE, seedState } from "./support";

const SAMPLE = path.join(__dirname, "fixtures", "rg-verso-ficticio.jpg");
const PAGE_SAMPLE = path.join(__dirname, "fixtures", "pagina-ficticia.jpg");

test.describe("administrador", () => {
  test.use({ storageState: ADMIN_STATE });

  test("filtros ficam na URL e sobrevivem ao recarregar", async ({ page }) => {
    await page.goto("/pessoas");
    await page.getByRole("combobox", { name: "Status" }).selectOption("reviewed");
    await expect(page).toHaveURL(/status=reviewed/);
    await page.getByPlaceholder("Nome ou CPF").fill("SOUZA");
    await expect(page).toHaveURL(/q=SOUZA/);
    await page.reload();
    await expect(page.getByPlaceholder("Nome ou CPF")).toHaveValue("SOUZA");
    await expect(page.getByText("com os filtros aplicados")).toBeVisible();
    await page.getByRole("button", { name: "Limpar filtros" }).click();
    await expect(page).toHaveURL(/\/pessoas$/);
  });

  test("lista carrega mais páginas ao rolar", async ({ page }) => {
    await page.goto("/pessoas");
    const rows = page.locator("tbody tr");
    await expect(rows).toHaveCount(50);
    await rows.last().scrollIntoViewIfNeeded();
    await expect(rows).not.toHaveCount(50);
  });

  test("envia frente e verso, revisa e salva", async ({ page }) => {
    await page.goto("/novo");
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByRole("button", { name: "Verso: Escolher arquivo" }).click()]);
    await chooser.setFiles({ name: "verso.jpg", mimeType: "image/jpeg", buffer: readFileSync(SAMPLE) });
    await page.getByRole("button", { name: "Extrair dados" }).click();
    await expect(page).toHaveURL(/\/documentos\/\d+/, { timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "Revisão dos dados" })).toBeVisible();
    await expect(page.getByText("Confiança média")).toBeVisible();
    const name = page.getByLabel(/Nome/).first();
    await name.fill("MARIA FICTICIA REVISADA");
    await expect(page.getByText("Alterações não salvas")).toBeVisible();
    await page.getByRole("button", { name: "Confirmar revisão" }).click();
    await expect(page.getByText("Revisão salva.")).toBeVisible();
  });

  test("lê uma página de livro, revisa, exporta e encontra na busca", async ({ page }) => {
    await page.goto("/leitura");
    await page.getByText("Livros e textos").click();
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByRole("button", { name: /Escolher arquivo/ }).first().click()]);
    await chooser.setFiles({ name: "pagina.jpg", mimeType: "image/jpeg", buffer: readFileSync(PAGE_SAMPLE) });
    await page.getByRole("button", { name: "Ler", exact: true }).click();
    await expect(page).toHaveURL(/\/registros\/\d+/, { timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "Dados lidos" })).toBeVisible();
    await expect(page.getByText(/cooperativa/i).first()).toBeVisible();
    const title = page.getByLabel(/Título/).first();
    await title.fill("Relatório fictício revisado");
    await page.getByRole("button", { name: "Confirmar revisão" }).click();
    await expect(page.getByText("Revisão salva.")).toBeVisible();
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exportar TXT" }).click()]);
    expect(download.suggestedFilename()).toMatch(/\.txt$/);
    await page.goto("/busca?q=revisado");
    await expect(page.getByRole("link", { name: /Relatório fictício revisado/ })).toBeVisible();
  });

  test("cartão mostra só o final e nunca o CVV", async ({ page }) => {
    await page.goto(`/registros/${seedState().card_record_id}`);
    await expect(page.getByLabel("Número")).toHaveValue("•••• •••• •••• 1111");
    await expect(page.getByText("Número completo não guardado")).toBeVisible();
    await expect(page.getByText("987")).toHaveCount(0);
    await expect(page.getByText("4111 1111 1111 1111")).toHaveCount(0);
  });

  test("apagar pessoa exige digitar nome ou CPF", async ({ page }) => {
    await page.goto(`/pessoas/${seedState().person_id}`);
    await page.getByRole("button", { name: "Apagar", exact: true }).click();
    const dialog = page.getByRole("alertdialog");
    const confirm = dialog.getByRole("button", { name: "Apagar definitivamente" });
    await expect(confirm).toBeDisabled();
    await dialog.getByRole("textbox").fill("nome errado");
    await expect(confirm).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("tema escuro e idioma inglês são lembrados", async ({ page }) => {
    await page.goto("/conta");
    await page.getByRole("button", { name: "Escuro" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByLabel("Idioma da interface").selectOption("en");
    await expect(page.getByRole("heading", { name: "My account" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "My account" })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByLabel("Interface language").selectOption("pt-BR");
    await page.getByRole("button", { name: "Sistema" }).click();
  });

  test("convite gera link de uso único sem SMTP", async ({ page, browser }) => {
    await page.goto("/usuarios");
    await page.getByLabel("E-mail").fill("convidada@exemplo.com.br");
    await page.getByLabel("Papel").first().selectOption("reviewer");
    await page.getByRole("button", { name: "Enviar convite" }).click();
    const link = await page.locator('input[readonly][value*="/convite/"]').inputValue();
    const guest = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const invited = await guest.newPage();
    await invited.goto(new URL(link).pathname);
    await expect(invited.getByText("convidada@exemplo.com.br")).toBeVisible();
    await invited.getByLabel("Seu nome").fill("Clara Convidada");
    await invited.getByLabel("Nova senha").fill("chave-forte-de-teste-7");
    await invited.getByLabel("Repita a senha").fill("chave-forte-de-teste-7");
    await invited.getByRole("button", { name: "Criar conta" }).click();
    await expect(invited).toHaveURL(/\/pessoas/);
    await invited.goto(new URL(link).pathname);
    await expect(invited.getByRole("heading", { name: "Convite indisponível" })).toBeVisible();
    await guest.close();
  });

  test("retorno do login não aceita endereço externo", async ({ browser }) => {
    const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
    const page = await context.newPage();
    await page.goto("/entrar?next=//exemplo.invalid/roubo");
    await page.getByLabel("E-mail").fill("admin@exemplo.com.br");
    await page.getByLabel("Senha", { exact: true }).fill("senha-de-teste-e2e-1");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL(/127\.0\.0\.1:\d+\/pessoas$/);
    await context.close();
  });
});

test.describe("leitor", () => {
  test.use({ storageState: READER_STATE });

  test("vê dados mas não envia, revisa nem administra", async ({ page }) => {
    await page.goto("/pessoas");
    await expect(page.getByRole("link", { name: "Novo documento" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Usuários" })).toHaveCount(0);
    await page.goto(`/documentos/${seedState().document_id}`);
    await expect(page.getByText("Seu papel permite apenas consultar este documento.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirmar revisão" })).toHaveCount(0);
    await page.goto(`/registros/${seedState().record_id}`);
    await expect(page.getByText("Seu papel permite apenas consultar este registro.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Nova leitura" })).toHaveCount(0);
    await page.goto("/leitura");
    await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
    await page.goto("/usuarios");
    await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
    const response = await page.request.get("/api/users");
    expect(response.status()).toBe(403);
  });
});

test("rota protegida sem sessão volta para o login", async ({ browser }) => {
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await page.goto("/documentos");
  await expect(page).toHaveURL(/\/entrar\?next=%2Fdocumentos/);
  await context.close();
});
