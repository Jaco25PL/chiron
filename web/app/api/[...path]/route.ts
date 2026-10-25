import { createHmac } from "node:crypto";
import type { NextRequest } from "next/server";
import { auth } from "@/auth";

// Server-side proxy from the browser to the FastAPI backend. It checks the Google session and
// forwards the request with the student's identity signed with CHIRON_BACKEND_SECRET, so the
// backend can trust who is calling (see api/security.py). /api/auth/* is handled by Auth.js,
// whose more specific route takes precedence over this catch-all.

// In dev the backend defaults to the local server; in a deployment CHIRON_API_URL must be set.
const API_URL =
  process.env.CHIRON_API_URL ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
const SECRET = process.env.CHIRON_BACKEND_SECRET;

const SIN_BACKEND =
  "El servidor de casos no está disponible en este momento. En la versión online todavía no está desplegado; probalo en local.";

export const maxDuration = 60; // patient + router replies can take several seconds

async function forward(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "Iniciá sesión para continuar." }, { status: 401 });
  if (!API_URL) return Response.json({ error: SIN_BACKEND }, { status: 503 });

  const { path } = await ctx.params;
  const name = encodeURIComponent(session.user?.name ?? "");
  const ts = String(Math.floor(Date.now() / 1000));
  const headers: Record<string, string> = {
    "content-type": req.headers.get("content-type") ?? "application/json",
    "x-chiron-user": email,
    "x-chiron-name": name,
    "x-chiron-ts": ts,
  };
  if (SECRET) {
    headers["x-chiron-sig"] = createHmac("sha256", SECRET).update(`${email}\n${name}\n${ts}`).digest("hex");
  }

  try {
    const res = await fetch(`${API_URL}/api/${path.join("/")}${req.nextUrl.search}`, {
      method: req.method,
      headers,
      body: req.method === "GET" ? undefined : await req.text(),
      cache: "no-store",
    });
    return new Response(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ error: SIN_BACKEND }, { status: 502 });
  }
}

export { forward as GET, forward as POST };
