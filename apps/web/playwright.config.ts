import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for the Kepler Vision E2E suite.
 *
 * The web app and the API are expected to be running:
 *   - API:  http://localhost:8000  (uvicorn kepler.main:app)
 *   - Web:  http://localhost:3000  (next dev / pnpm dev)
 *
 * In CI the workflow brings them up via the dev docker-compose stack.
 */
const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const webUrl = process.env.PLAYWRIGHT_WEB_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: webUrl,
    actionTimeout: 5_000,
    navigationTimeout: 10_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: process.env.CI
    ? undefined
    : {
        command: "echo 'expecting web + api to be running locally'",
        url: `${webUrl}/`,
        reuseExistingServer: true,
        timeout: 5_000,
      },
  globalSetup: async () => {
    // Probe the API; fail loud if it isn't reachable.
    try {
      const r = await fetch(`${apiUrl}/healthz`);
      if (!r.ok) throw new Error(`API healthz returned ${r.status}`);
    } catch (err) {
      throw new Error(
        `API is not reachable at ${apiUrl}. Start it with: cd services/api && uvicorn kepler.main:app --port 8000`,
      );
    }
  },
});
