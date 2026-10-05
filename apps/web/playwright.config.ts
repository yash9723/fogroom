import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests expect the API (http://localhost:8000) and Postgres/Redis to be running with
 * demo data seeded (`./scripts/dev.ps1 seed`). The web app is started automatically.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 240_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "pnpm dev",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 180_000,
      },
});
