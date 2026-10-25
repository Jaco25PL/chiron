import { expect, test } from "@playwright/test";
import { signInAs } from "./session";

// The web → backend path: signed requests through the Next proxy, and per-user ownership.
// Locally/CI it hits the fake backend; with BASE_URL it hits the deployed one.

test.beforeEach(async ({ context, baseURL }) => signInAs(context, baseURL!));

test("signed requests reach the backend through the Next proxy", async ({ page }) => {
  const res = await page.request.get("/api/cases");
  expect(res.status()).toBe(200);
  const cases = await res.json();
  expect(cases.length).toBeGreaterThan(0);
  expect(JSON.stringify(cases)).not.toContain("diagnostico"); // the hidden diagnosis never leaves the backend
});

test("a consultation belongs to its creator", async ({ page, browser, baseURL }) => {
  const created = await page.request.post("/api/sessions", { data: { case_id: "mpna-disnea-icc", mode: "chat" } });
  expect(created.status()).toBe(200);
  const { session_id } = await created.json();
  expect((await page.request.get(`/api/sessions/${session_id}`)).status()).toBe(200);

  const other = await browser.newContext();
  await signInAs(other, baseURL!, { user: { name: "Otro", email: "otro@example.com", picture: null } });
  const res = await (await other.newPage()).request.get(`/api/sessions/${session_id}`);
  expect(res.status()).toBe(403);
  await other.close();
});
