import type { NextConfig } from "next";

// The backend (FastAPI + LangGraph) runs separately; Next exposes it under /api.
// In dev it defaults to the local server; in a deployment it is only proxied when CHIRON_API_URL is set
// (otherwise /api/* 404s and the UI says the backend is unavailable).
const API_URL = process.env.CHIRON_API_URL ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : null);

const nextConfig: NextConfig = {
  devIndicators: false, // the dev indicator covered the mic button on mobile
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
  rewrites() {
    // `fallback` runs after every Next route, including dynamic ones like /api/auth/[...nextauth];
    // a plain array would run before dynamic routes and send Auth.js requests to FastAPI.
    const fallback = API_URL ? [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }] : [];
    return { beforeFiles: [], afterFiles: [], fallback };
  },
};

export default nextConfig;
