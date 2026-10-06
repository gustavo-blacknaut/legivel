import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import type { Account } from "./accounts";

export const STATE_DIR = path.join(__dirname, ".state");
export const ADMIN_STATE = path.join(STATE_DIR, "admin.json");
export const READER_STATE = path.join(STATE_DIR, "reader.json");
export const WIDTHS = [360, 375, 768, 1024, 1280, 1920] as const;
export const ZOOMED = { width: 640, label: "1280 com zoom de 200%" };

export type SeedState = { document_id: number; person_id: number; scan_token: string };

export function seedState(): SeedState {
  return JSON.parse(readFileSync(path.join(STATE_DIR, "state.json"), "utf-8")) as SeedState;
}

export async function signIn(page: Page, account: Account): Promise<void> {
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(account.email);
  await page.getByLabel("Senha", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/pessoas/);
}

export async function horizontalOverflow(page: Page): Promise<{ overflow: number; offenders: string[] }> {
  return page.evaluate(() => {
    const root = document.documentElement;
    const overflow = root.scrollWidth - root.clientWidth;
    const offenders: string[] = [];
    if (overflow > 0) {
      for (const element of Array.from(document.body.querySelectorAll<HTMLElement>("*"))) {
        const rect = element.getBoundingClientRect();
        if (rect.right > root.clientWidth + 1 && rect.width > 0 && getComputedStyle(element).position !== "fixed") {
          offenders.push(`${element.tagName.toLowerCase()}.${element.className.toString().split(" ")[0] ?? ""} (${Math.round(rect.right)}px)`);
        }
        if (offenders.length >= 5) break;
      }
    }
    return { overflow, offenders };
  });
}

export async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const selector = "button, a[href], input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, [role=button], summary";
    const problems: string[] = [];
    for (const element of Array.from(document.querySelectorAll<HTMLElement>(selector))) {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden" || element.closest("[aria-hidden=true]")) continue;
      if (element.closest(".visually-hidden") || element.classList.contains("visually-hidden")) continue;
      if (element.tagName === "A" && element.closest("p, dd, li span")) continue;
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      if (rect.height < 43.5 || rect.width < 43.5) {
        const label = (element.getAttribute("aria-label") ?? element.textContent ?? "").trim().slice(0, 40);
        problems.push(`${element.tagName.toLowerCase()} "${label}" ${Math.round(rect.width)}x${Math.round(rect.height)}`);
      }
    }
    return problems;
  });
}
