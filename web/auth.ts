import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Google sign-in via Auth.js. Sessions are stateless encrypted JWT cookies (no database).
// Env: AUTH_SECRET, AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET (see web/.env.local).
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  pages: { signIn: "/login" },
  callbacks: {
    // Used by proxy.ts: every route except the public ones requires a session.
    authorized({ auth, request }) {
      const { pathname } = request.nextUrl;
      const isPublic = pathname === "/login" || pathname.startsWith("/api/auth");
      return isPublic || !!auth?.user;
    },
  },
});
