import { expect, test, type Page } from "@playwright/test";
import { ADMIN_STATE, WIDTHS, ZOOMED, horizontalOverflow, seedState, smallTargets } from "./support";

const HEIGHT = 900;

function privateRoutes(): string[] {
  const state = seedState();
  return [
    "/pessoas",
    `/pessoas/${state.person_id}`,
    "/documentos",
    `/documentos/${state.document_id}`,
    "/novo",
    "/auditoria",
    "/conta",
    "/usuarios",
    "/configuracoes",
  ];
}

function publicRoutes(): string[] {
  return ["/entrar", "/redefinir-senha", `/enviar/${seedState().scan_token}`, "/convite/convite-inexistente-123", "/configuracao-inicial"];
}

async function open(page: Page, route: string): Promise<void> {
  await page.goto(route);
  await page.waitForLoadState("networkidle");
  await expect(page.locator("h1").first()).toBeVisible();
}

const sizes = [...WIDTHS.map((width) => ({ width, label: `${width}px` })), ZOOMED];

for (const size of sizes) {
  test.describe(`largura ${size.label}`, () => {
    test.use({ viewport: { width: size.width, height: HEIGHT } });

    test.describe("logado", () => {
      test.use({ storageState: ADMIN_STATE });

      test("nenhuma rota tem rolagem horizontal", async ({ page }) => {
        for (const route of privateRoutes()) {
          await open(page, route);
          const result = await horizontalOverflow(page);
          expect(result.overflow, `${route}: ${result.offenders.join(", ")}`).toBeLessThanOrEqual(0);
        }
      });

      if (size.width <= 1024) {
        test("alvos de toque têm pelo menos 44 px", async ({ page }) => {
          for (const route of privateRoutes()) {
            await open(page, route);
            const problems = await smallTargets(page);
            expect(problems, route).toEqual([]);
          }
        });
      }
    });

    test.describe("sem login", () => {
      test("telas públicas sem rolagem horizontal", async ({ page }) => {
        for (const route of publicRoutes()) {
          await open(page, route);
          const result = await horizontalOverflow(page);
          expect(result.overflow, `${route}: ${result.offenders.join(", ")}`).toBeLessThanOrEqual(0);
          if (size.width <= 1024) expect(await smallTargets(page), route).toEqual([]);
        }
      });
    });
  });
}

test.describe("celular", () => {
  test.use({ viewport: { width: 375, height: 812 }, storageState: ADMIN_STATE, hasTouch: true });

  test("menu lateral vira gaveta", async ({ page }) => {
    await open(page, "/pessoas");
    const sidebar = page.getByRole("complementary", { name: "Navegação principal" });
    await expect(sidebar).toBeHidden();
    await page.getByRole("button", { name: "Abrir menu" }).click();
    await expect(sidebar).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sidebar).toBeHidden();
  });

  test("modal de apagar abre como bottom sheet", async ({ page }) => {
    await open(page, "/pessoas");
    await page.getByRole("button", { name: /^Apagar / }).first().click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(Math.round((box?.y ?? 0) + (box?.height ?? 0))).toBeGreaterThanOrEqual(811);
    expect(Math.round(box?.width ?? 0)).toBe(375);
    await page.getByRole("button", { name: "Cancelar" }).click();
    await expect(dialog).toBeHidden();
  });

  test("botões principais da revisão ficam ao alcance do polegar", async ({ page }) => {
    await open(page, `/documentos/${seedState().document_id}`);
    const confirm = page.getByRole("button", { name: "Confirmar revisão" });
    await confirm.scrollIntoViewIfNeeded();
    const box = await confirm.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    expect(box?.width ?? 0).toBeGreaterThan(300);
  });

  test("captura oferece câmera traseira", async ({ page }) => {
    await open(page, "/novo");
    await expect(page.locator('input[type=file][capture="environment"]')).toHaveCount(2);
    await expect(page.getByRole("button", { name: "Frente: Tirar foto" })).toBeVisible();
  });
});

test.describe("preferências do sistema", () => {
  test.use({ storageState: ADMIN_STATE });

  test("respeita prefers-color-scheme", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await open(page, "/pessoas");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.emulateMedia({ colorScheme: "light" });
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("respeita prefers-reduced-motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await open(page, "/pessoas");
    const duration = await page.evaluate(() => getComputedStyle(document.querySelector("main, div") as Element).transitionDuration);
    expect(duration.split(",").every((value) => parseFloat(value) <= 0.001)).toBe(true);
  });

  test("viewport cobre a área segura", async ({ page }) => {
    await open(page, "/pessoas");
    await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /viewport-fit=cover/);
  });
});
