import { defineConfig } from "@playwright/test";

// E2E tests for the web app. Deterministic: Google is never contacted (the OAuth redirect is
// intercepted) and signed-in state uses a session cookie minted with AUTH_SECRET.
//   npm run test:e2e                                   # local dev server (started if needed)
//   BASE_URL=https://chiron-nu-two.vercel.app npm run test:e2e   # smoke test against prod
const baseURL = process.env.BASE_URL ?? "http://localhost:3000";
const local = baseURL.startsWith("http://localhost");

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL, channel: "chrome", trace: "retain-on-failure" },
  webServer: local
    ? { command: "npm run dev -- --port 3000", url: "http://localhost:3000/login", reuseExistingServer: true, timeout: 120_000 }
    : undefined,
});
