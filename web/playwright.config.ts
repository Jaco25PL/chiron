import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

// E2E tests. Two modes:
//
//   npm run test:e2e
//     Self-contained (local and CI): starts the FastAPI backend in fake mode (keyword replies from
//     the real cases, no LLM) and a production build of the web app, wired together with the
//     signed-identity proxy. Deterministic: Google is never contacted (the OAuth redirect is
//     intercepted) and signed-in state uses a session cookie minted with AUTH_SECRET.
//
//   BASE_URL=https://chiron-nu-two.vercel.app npm run test:e2e
//     Smoke test against a deployment (real backend + Gemini).

const external = process.env.BASE_URL;
const WEB_PORT = 3100;
const API_PORT = 8001;

/** Same AUTH_SECRET for the web server and for the cookies the tests mint (tests/e2e/session.ts). */
function authSecret() {
  if (process.env.AUTH_SECRET) return process.env.AUTH_SECRET;
  const env = existsSync(".env.local") ? readFileSync(".env.local", "utf-8") : "";
  const line = env.split(/\r?\n/).find((l) => l.startsWith("AUTH_SECRET="));
  if (!line) throw new Error("Set AUTH_SECRET (or create web/.env.local)");
  process.env.AUTH_SECRET = line.slice("AUTH_SECRET=".length);
  return process.env.AUTH_SECRET;
}

// absolute path: the API server runs with cwd = repo root, and Windows' cmd doesn't take "../x"
const python =
  process.env.E2E_PYTHON ?? (process.platform === "win32" ? `"${resolve(__dirname, "..", ".venv", "Scripts", "python.exe")}"` : "python");
const BACKEND_SECRET = "e2e-backend-secret";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  fullyParallel: true,
  // headless Chrome renders the backdrop blurs in software: more parallel browsers starve each other and
  // time out (2 is also faster than the default half of the cores)
  workers: 2,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: { baseURL: external ?? `http://localhost:${WEB_PORT}`, channel: "chrome", trace: "retain-on-failure" },
  webServer: external
    ? undefined
    : [
        {
          name: "api (fake)",
          command: `${python} -m uvicorn api.main:app --port ${API_PORT}`,
          cwd: "..",
          url: `http://127.0.0.1:${API_PORT}/api/health`,
          env: {
            CHIRON_FAKE: "1",
            CHIRON_BACKEND_SECRET: BACKEND_SECRET,
            CHIRON_REVIEWERS: "revisora@example.com",
            DATABASE_URL: "",
            PYTHONIOENCODING: "utf-8",
          },
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
        {
          name: "web",
          command: `npm run build && npm run start -- --port ${WEB_PORT}`,
          url: `http://localhost:${WEB_PORT}/login`,
          env: {
            AUTH_SECRET: authSecret(),
            AUTH_GOOGLE_ID: process.env.AUTH_GOOGLE_ID ?? "e2e-client-id.apps.googleusercontent.com",
            AUTH_GOOGLE_SECRET: process.env.AUTH_GOOGLE_SECRET ?? "e2e-client-secret",
            AUTH_TRUST_HOST: "true",
            CHIRON_API_URL: `http://127.0.0.1:${API_PORT}`,
            CHIRON_BACKEND_SECRET: BACKEND_SECRET,
          },
          reuseExistingServer: !process.env.CI,
          timeout: 240_000,
        },
      ],
});
