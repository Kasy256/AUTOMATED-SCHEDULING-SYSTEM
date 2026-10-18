import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 180_000,
  // Sign-up hashes passwords and this dev host commits slowly; 5 s flakes.
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    // E2E_VIDEO=1 records every test, e.g. for a demo of WEB-01.
    video: process.env.E2E_VIDEO === "1" ? "on" : "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /me-phone\.spec\.ts/,
    },
    {
      name: "phone",
      use: { ...devices["Pixel 7"] },
      testMatch: /(smoke|me-phone)\.spec\.ts/,
    },
  ],
  webServer: [
    {
      // Repo root, so pydantic-settings reads .env; env vars below override it.
      command:
        "uv run uvicorn cartlyf_api.main:create_app --factory --port 8000",
      cwd: "../..",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      env: {
        CARTLYF_AUTH_RATE_LIMIT_PER_MINUTE: "1000",
        CARTLYF_COOKIE_SECURE: "false",
      },
      timeout: 120_000,
    },
    {
      command: "pnpm dev --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // WEB-06 measures a production build; dev-mode React is several times slower.
      command:
        "pnpm exec vite build && pnpm exec vite preview --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
    },
  ],
});
