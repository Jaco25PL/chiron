import type { NextRequest } from "next/server";
import { auth } from "@/auth";
import { API_URL, backendFetch } from "@/lib/backend";

// Server-side proxy from the browser to the FastAPI backend. It checks the Google session and
// forwards the request with the student's identity signed (lib/backend.ts), so the backend can
// trust who is calling (see api/security.py). /api/auth/* is handled by Auth.js, whose more
// specific route takes precedence over this catch-all.

const SIN_BACKEND =
  "El servidor de casos no está disponible en este momento. En la versión online todavía no está desplegado; probalo en local.";

export const maxDuration = 60; // patient + router replies can take several seconds

async function forward(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) return Response.json({ error: "Iniciá sesión para continuar." }, { status: 401 });
  if (!API_URL) return Response.json({ error: SIN_BACKEND }, { status: 503 });

  const { path } = await ctx.params;
  try {
    const res = await backendFetch(
      `/api/${path.join("/")}${req.nextUrl.search}`,
      { email, nombre: session.user?.name },
      {
        method: req.method,
        headers: { "content-type": req.headers.get("content-type") ?? "application/json" },
        body: req.method === "GET" ? undefined : await req.text(),
      },
    );
    return new Response(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ error: SIN_BACKEND }, { status: 502 });
  }
}

export { forward as GET, forward as POST };
