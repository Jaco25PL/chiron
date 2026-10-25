// Next 16 "proxy" (formerly middleware): redirects signed-out users to /login using the
// `authorized` callback in auth.ts. Also guards the /api/* calls proxied to the backend.
export { auth as proxy } from "@/auth";

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|retratos/).*)"],
};
