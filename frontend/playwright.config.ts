import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3008",
    trace: "off",
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
