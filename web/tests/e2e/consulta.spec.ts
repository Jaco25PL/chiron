import { expect, test } from "@playwright/test";
import { signInAs } from "./session";

// UI behavior of the consultation screen with the backend mocked (deterministic, no LLM).

test.beforeEach(async ({ context, baseURL }) => signInAs(context, baseURL!));

test("a slow cold start shows a 'waking up' notice, which goes away once ready", async ({ page }) => {
  await page.route("**/api/cases**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/sessions", async (route) => {
    await new Promise((r) => setTimeout(r, 5000)); // backend scaled to zero, starting up
    await route.fulfill({ json: { session_id: "s1" } });
  });
  await page.goto("/consulta/mpna-disnea-icc?modo=chat");
  await expect(page.getByRole("status")).toContainText("Preparando la consulta", { timeout: 6000 });
  await expect(page.getByRole("status")).toBeHidden({ timeout: 6000 });
});

test("a fast backend never shows the notice", async ({ page }) => {
  await page.route("**/api/cases**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/sessions", (route) => route.fulfill({ json: { session_id: "s1" } }));
  await page.goto("/consulta/mpna-disnea-icc?modo=chat");
  await page.waitForTimeout(4500);
  await expect(page.getByRole("status")).toHaveCount(0);
});
