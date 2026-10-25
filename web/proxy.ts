// Next 16 "proxy" (formerly middleware): redirects signed-out users to /login using the
// `authorized` callback in auth.ts.
//
// /api is excluded on purpose: the proxy re-issues the session cookie on every response, so a
// slow API response arriving after sign-out would bring the session back. API routes check the
// session themselves (app/api/[...path]/route.ts answers 401) and never rewrite the cookie.
export { auth as proxy } from "@/auth";

export const config = {
  matcher: ["/((?!api/|_next/static|_next/image|favicon.ico|retratos/).*)"],
};
