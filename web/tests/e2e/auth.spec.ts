import { expect, test } from "@playwright/test";
import { signInAs, TEST_USER } from "./session";

test.describe("signed out", () => {
  for (const path of ["/", "/consulta/mpna-disnea-icc?modo=cara"]) {
    test(`page ${path} redirects to /login and keeps the destination`, async ({ page, baseURL }) => {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login\?/);
      const callback = new URL(page.url()).searchParams.get("callbackUrl")!;
      expect(new URL(callback, baseURL).pathname + new URL(callback, baseURL).search).toBe(path);
      await expect(page.getByRole("button", { name: "Continuar con Google" })).toBeVisible();
    });
  }

  test("backend API is not reachable without a session", async ({ request }) => {
    const res = await request.get("/api/cases", { maxRedirects: 0 });
    expect(res.status()).toBe(401);
    expect((await res.json()).error).toBeTruthy();
  });

  test("session endpoint reports no user", async ({ request }) => {
    expect(await (await request.get("/api/auth/session")).json()).toBeNull();
  });

  test("Google is the configured provider", async ({ request, baseURL }) => {
    const providers = await (await request.get("/api/auth/providers")).json();
    expect(providers.google.callbackUrl).toBe(`${baseURL}/api/auth/callback/google`);
  });

  test("'Continuar con Google' sends a correct OAuth request (Google itself is not contacted)", async ({ page, baseURL }) => {
    let authorize: URL | null = null;
    await page.route("https://accounts.google.com/**", (route) => {
      authorize = new URL(route.request().url());
      return route.fulfill({ status: 200, body: "intercepted" });
    });
    await page.goto("/login");
    await page.getByRole("button", { name: "Continuar con Google" }).click();
    await expect.poll(() => authorize).not.toBeNull();
    const q = authorize!.searchParams;
    // this exact URI must be registered in the GCP OAuth client, or Google answers redirect_uri_mismatch
    expect(q.get("redirect_uri")).toBe(`${baseURL}/api/auth/callback/google`);
    expect(q.get("client_id")).toMatch(/\.apps\.googleusercontent\.com$/);
    expect(q.get("response_type")).toBe("code");
    expect(q.get("scope")?.split(" ").sort()).toEqual(["email", "openid", "profile"]);
    expect(q.get("code_challenge_method")).toBe("S256"); // PKCE
  });

  test("a session cookie signed with the wrong secret is rejected", async ({ page, context, baseURL }) => {
    await signInAs(context, baseURL!, { secret: "not-the-real-secret-not-the-real-secret" });
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("signed in", () => {
  test.beforeEach(async ({ context, baseURL }) => signInAs(context, baseURL!));

  test("home loads and shows the account menu", async ({ page }) => {
    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login/);
    await page.getByRole("button", { name: "Cuenta" }).click();
    await expect(page.getByText(TEST_USER.email)).toBeVisible();
  });

  test("session endpoint returns the user", async ({ page }) => {
    // page.request shares the browser context's cookies (the `request` fixture does not)
    const session = await (await page.request.get("/api/auth/session")).json();
    expect(session.user.email).toBe(TEST_USER.email);
  });

  test("/login sends a signed-in user to the callback path", async ({ page }) => {
    await page.goto("/login?callbackUrl=%2Fconsulta%2Fmpna-disnea-icc");
    await expect(page).toHaveURL(/\/consulta\/mpna-disnea-icc$/);
  });

  test("/login never redirects to another site (open redirect)", async ({ page, baseURL }) => {
    await page.goto("/login?callbackUrl=https%3A%2F%2Fevil.example%2Fsteal");
    expect(new URL(page.url()).origin).toBe(new URL(baseURL!).origin);
    await expect(page).toHaveURL(/\/steal$/); // only the path survives, on our own origin
  });

  test("signing out clears the session, even with an API call still in flight", async ({ page }) => {
    // hold the cases request until after sign-out: its late response must not restore the session
    let release!: () => void;
    const held = new Promise<void>((r) => (release = r));
    await page.route("**/api/cases**", async (route) => {
      await held;
      await route.continue();
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Cuenta" }).click();
    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    // sign-out is a server action; in dev its first call compiles on demand, which can exceed 5s
    await expect(page).toHaveURL(/\/login/, { timeout: 20_000 });
    release();
    await page.waitForTimeout(500);
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("backend unavailable", () => {
  test.beforeEach(async ({ context, baseURL }) => signInAs(context, baseURL!));

  test("a missing backend shows a clear message instead of a bare 404", async ({ page }) => {
    await page.route("**/api/cases**", (route) => route.fulfill({ status: 404, body: "Not Found" }));
    await page.goto("/");
    await expect(page.getByText("El servidor de casos no está disponible")).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/); // the user stays signed in
  });
});
