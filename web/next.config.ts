import type { NextConfig } from "next";

// /api/* (except /api/auth) is proxied to the FastAPI backend by app/api/[...path]/route.ts,
// which also signs the user's identity for the backend.
const nextConfig: NextConfig = {
  devIndicators: false, // the dev indicator covered the mic button on mobile
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
};

export default nextConfig;
