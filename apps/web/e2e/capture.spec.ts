import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { ADMIN_STATE } from "./support";

const SAMPLE = path.join(__dirname, "fixtures", "rg-verso-ficticio.jpg");

test.describe("captura e duplicidade", () => {
  test.use({ storageState: ADMIN_STATE });

  test("câmera guiada captura, confere as bordas e encerra o vídeo", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: async () => {
          const canvas = document.createElement("canvas");
          canvas.width = 1280;
          canvas.height = 960;
          const context = canvas.getContext("2d")!;
          const draw = () => {
            context.fillStyle = "#222";
            context.fillRect(0, 0, 1280, 960);
            context.fillStyle = "#eee";
            context.fillRect(160, 180, 960, 600);
            context.fillStyle = "#111";
            context.font = "48px sans-serif";
            context.fillText("DOCUMENTO FICTICIO", 220, 320);
            context.fillText("123456789", 220, 450);
          };
          draw();
          const media = canvas.captureStream(10);
          setInterval(draw, 100);
          (window as unknown as Window & { cameraStream: MediaStream }).cameraStream = media;
          return media;
        },
      });
    });
    await page.goto("/novo");
    await page.getByRole("button", { name: "Câmera guiada", exact: true }).first().click();
    const dialog = page.getByRole("dialog", { name: "Câmera guiada" });
    await expect(dialog).toBeVisible();
    await expect.poll(() => dialog.locator("video").evaluate((element) => (element as HTMLVideoElement).videoWidth)).toBeGreaterThan(0);
    const response = page.waitForResponse((item) => item.url().includes("/api/capture/check") && item.status() === 200);
    await dialog.getByRole("button", { name: "Capturar", exact: true }).click();
    const quality = await (await response).json();
    expect(quality.corners).toHaveLength(4);
    await expect(dialog).toBeHidden();
    await expect(page.getByText("Os avisos são estimativas; confira a foto antes de enviar.")).toBeVisible();
    await expect.poll(() => page.evaluate(() => (window as unknown as Window & { cameraStream: MediaStream }).cameraStream.getTracks().every((track) => track.readyState === "ended"))).toBe(true);
  });

  test("câmera recusada oferece a captura nativa do aparelho", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: async () => { throw new DOMException("Recusado", "NotAllowedError"); },
      });
    });
    await page.goto("/novo");
    await page.getByRole("button", { name: "Câmera guiada", exact: true }).first().click();
    const dialog = page.getByRole("dialog", { name: "Câmera guiada" });
    await expect(dialog.getByText("Câmera indisponível. Use a opção de foto do aparelho.")).toBeVisible();
    const chooser = page.waitForEvent("filechooser");
    await dialog.getByRole("button", { name: "Capturar", exact: true }).click();
    await (await chooser).setFiles(SAMPLE);
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: "Remover", exact: true })).toBeVisible();
  });

  test("documento duplicado permite abrir existente e manter uma cópia", async ({ page }) => {
    await page.goto("/novo");
    const file = { name: "duplicado.jpg", mimeType: "image/jpeg", buffer: Buffer.concat([readFileSync(SAMPLE), Buffer.from("e2e-duplicate-only")]) };
    const queued = await page.request.post("/api/jobs", {
      headers: { "X-Requested-With": "legivel" },
      multipart: { duplicate: "keep", front: file },
    });
    expect(queued.status()).toBe(202);
    const job = await queued.json();
    await expect.poll(async () => {
      const jobs = await (await page.request.get("/api/jobs")).json();
      return jobs.find((item: { id: number }) => item.id === job.id)?.status;
    }, { timeout: 60_000 }).toBe("completed");
    const conflict = await page.request.post("/api/jobs", {
      headers: { "X-Requested-With": "legivel" }, multipart: { front: file },
    });
    expect(conflict.status()).toBe(409);
    const existingId = (await conflict.json()).detail.document_id;
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Frente: Escolher arquivo" }).click();
    await (await chooser).setFiles(file);
    await page.getByRole("button", { name: "Extrair dados" }).click();
    const dialog = page.getByRole("dialog", { name: "Este documento já existe" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("link", { name: "Abrir existente" })).toHaveAttribute("href", `/documentos/${existingId}`);
    await expect(dialog.getByRole("button", { name: "Substituir existente" })).toBeVisible();
    await dialog.getByRole("button", { name: "Manter nova cópia" }).click();
    await expect(page).toHaveURL(/\/fila$/);
    await expect(page.getByRole("article").filter({ hasText: "duplicado.jpg" }).first()).toBeVisible();
  });
});


