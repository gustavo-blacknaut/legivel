import { defineConfig, devices } from "@playwright/test";

const API_PORT = Number(process.env.E2E_API_PORT ?? 8010);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3010);
const python = process.env.LEGIVEL_PYTHON ?? "python";
const skipBuild = process.env.E2E_SKIP_BUILD === "1";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    { name: "flows", testMatch: /(flows|workflow|capture|maintenance)\.spec\.ts/, dependencies: ["setup"], use: { ...devices["Desktop Chrome"] } },
    { name: "responsive", testMatch: /responsive\.spec\.ts/, dependencies: ["setup"], use: { ...devices["Desktop Chrome"] } },
    { name: "screenshots", testMatch: /screenshots\.spec\.ts/, dependencies: ["setup"], use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: `${python} -m scripts.e2e_server --port ${API_PORT} --accounts ../web/e2e/accounts.json --state ../web/e2e/.state/state.json`,
      cwd: "../api",
      url: `http://127.0.0.1:${API_PORT}/health`,
      timeout: 240_000,
      reuseExistingServer: false,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: skipBuild ? `npm run start -- -p ${WEB_PORT}` : `npm run build && npm run start -- -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/entrar`,
      timeout: 300_000,
      reuseExistingServer: false,
      env: { LEGIVEL_API_URL: `http://127.0.0.1:${API_PORT}` },
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
});
