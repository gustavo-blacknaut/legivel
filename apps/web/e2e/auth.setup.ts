import { test as setup } from "@playwright/test";
import { ADMIN, READER } from "./accounts";
import { ADMIN_STATE, READER_STATE, signIn } from "./support";

setup("entra como administrador", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.context().storageState({ path: ADMIN_STATE });
});

setup("entra como leitor", async ({ page }) => {
  await signIn(page, READER);
  await page.context().storageState({ path: READER_STATE });
});
