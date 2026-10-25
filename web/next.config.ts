import type { NextConfig } from "next";

// /api/* (except /api/auth) is proxied to the FastAPI backend by app/api/[...path]/route.ts,
// which also signs the user's identity for the backend.
const nextConfig: NextConfig = {
  devIndicators: false, // the dev indicator covered the mic button on mobile
  // chiron-revision.vercel.app is an alias of this project, an easy link for the medical reviewers.
  // Sign-in only works on the main domain (the OAuth redirect URI registered with Google), so it redirects there.
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "chiron-revision.vercel.app" }],
        destination: "https://chiron-nu-two.vercel.app/revision",
        permanent: false,
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
};

export default nextConfig;
