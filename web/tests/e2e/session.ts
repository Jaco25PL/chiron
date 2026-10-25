import { readFileSync } from "node:fs";
import { join } from "node:path";
import { encode } from "@auth/core/jwt";
import type { BrowserContext } from "@playwright/test";

export const TEST_USER = { name: "Test Student", email: "student@example.com", picture: null };

/** AUTH_SECRET from the environment or web/.env.local (the same secret the server uses). */
export function authSecret(): string {
  if (process.env.AUTH_SECRET) return process.env.AUTH_SECRET;
  const env = readFileSync(join(__dirname, "..", "..", ".env.local"), "utf-8");
  const line = env.split(/\r?\n/).find((l) => l.startsWith("AUTH_SECRET="));
  if (!line) throw new Error("AUTH_SECRET not found in env or web/.env.local");
  return line.slice("AUTH_SECRET=".length).replace(/^"|"$/g, "");
}

/** Auth.js cookie name: secure prefix on https. The cookie name is also the JWE salt. */
export function cookieName(baseURL: string) {
  return baseURL.startsWith("https://") ? "__Secure-authjs.session-token" : "authjs.session-token";
}

/** Adds a valid (or deliberately forged) Auth.js session cookie to the browser context. */
export async function signInAs(
  context: BrowserContext,
  baseURL: string,
  { secret = authSecret(), user = TEST_USER }: { secret?: string; user?: typeof TEST_USER } = {},
) {
  const name = cookieName(baseURL);
  const value = await encode({ token: { ...user, sub: "test-user" }, secret, salt: name, maxAge: 3600 });
  // `url` (not `domain`) makes a host-only cookie, exactly what Auth.js sets and later deletes
  await context.addCookies([
    { name, value, url: baseURL, httpOnly: true, secure: baseURL.startsWith("https://"), sameSite: "Lax" },
  ]);
}
