import { expect, test, type Page } from "@playwright/test";
import { signInAs, TEST_USER } from "./session";

// The accent color picked in the settings: applied at once, saved per user in the backend and
// rendered by the server on <html data-acento>, so a reload (or another device) paints it first.

/** A user of our own: the fake backend keeps preferences in memory, shared by all tests. */
const usuario = () => ({
  ...TEST_USER,
  email: `acento-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`,
});

/** <html data-acento> exactly as the server sent it, before any script runs. */
async function acentoDelServidor(page: Page, path = "/") {
  const html = await (await page.request.get(path)).text();
  return html.match(/<html[^>]*\sdata-acento="([^"]+)"/)?.[1];
}

test("choosing Rosa changes the accent, is saved, and the server renders it after a reload", async ({
  page,
  context,
  browser,
  baseURL,
}) => {
  const user = usuario();
  await signInAs(context, baseURL!, { user });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-acento", "menta");

  await page.getByRole("button", { name: "Cuenta" }).click();
  await expect(page.getByRole("radio", { name: "Menta" })).toBeChecked();
  const guardado = page.waitForResponse(
    (r) => r.url().endsWith("/api/preferencias") && r.request().method() === "POST",
  );
  await page.getByRole("dialog").getByText("Rosa", { exact: true }).click(); // the label, like a user
  expect((await guardado).status()).toBe(200);

  await expect(page.locator("html")).toHaveAttribute("data-acento", "rosa");
  await expect(page.getByRole("radio", { name: "Rosa" })).toBeChecked();
  const accent = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--accent").trim(),
  );
  expect(accent.toLowerCase()).toBe("#ffb0d6");

  // same browser: the cookie makes the server render it
  expect(await acentoDelServidor(page)).toBe("rosa");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-acento", "rosa");

  // another device (no cookie): the server asks the backend before the first paint
  const otro = await browser.newContext();
  await signInAs(otro, baseURL!, { user });
  const otraPagina = await otro.newPage();
  expect(await acentoDelServidor(otraPagina)).toBe("rosa");
  await otro.close();
});

test("the color picker works with the keyboard", async ({ page, context, baseURL }) => {
  await signInAs(context, baseURL!, { user: usuario() });
  await page.goto("/");
  await page.getByRole("button", { name: "Cuenta" }).focus();
  await page.keyboard.press("Enter");
  const azul = page.getByRole("radio", { name: "Azul" });
  await expect(azul).toBeAttached();
  // native radios: Tab reaches the checked one, the arrows move through the group (and pick)
  for (let i = 0; i < 10 && !(await page.getByRole("radio", { name: "Menta" }).evaluate((el) => el === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  for (let i = 0; i < 10 && !(await azul.isChecked()); i++) await page.keyboard.press("ArrowDown");
  await expect(page.locator("html")).toHaveAttribute("data-acento", "azul");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
});

test("signed out, /login is rendered with the default accent", async ({ page }) => {
  expect(await acentoDelServidor(page, "/login")).toBe("menta");
});
