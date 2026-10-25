import "server-only";
import { createHmac } from "node:crypto";

// Server-side access to the FastAPI backend with the student's identity signed with
// CHIRON_BACKEND_SECRET, so the backend can trust who is calling (see api/security.py).
// Used by the browser proxy (app/api/[...path]/route.ts) and by server components.

// In dev the backend defaults to the local server; in a deployment CHIRON_API_URL must be set.
export const API_URL =
  process.env.CHIRON_API_URL ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
const SECRET = process.env.CHIRON_BACKEND_SECRET;

/** Identity headers for the backend: x-chiron-user/-name/-ts, plus the HMAC when a secret is set. */
export function identidad(email: string, nombre: string | null | undefined): Record<string, string> {
  const name = encodeURIComponent(nombre ?? "");
  const ts = String(Math.floor(Date.now() / 1000));
  const headers: Record<string, string> = { "x-chiron-user": email, "x-chiron-name": name, "x-chiron-ts": ts };
  if (SECRET) {
    headers["x-chiron-sig"] = createHmac("sha256", SECRET).update(`${email}\n${name}\n${ts}`).digest("hex");
  }
  return headers;
}

/** fetch to the backend as this user. Throws if there is no backend configured or it can't be reached. */
export function backendFetch(
  path: string,
  usuario: { email: string; nombre?: string | null },
  init: RequestInit = {},
): Promise<Response> {
  if (!API_URL) return Promise.reject(new Error("CHIRON_API_URL is not set"));
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...(init.headers as Record<string, string>), ...identidad(usuario.email, usuario.nombre) },
    cache: "no-store",
  });
}
