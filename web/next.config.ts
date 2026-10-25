import type { NextConfig } from "next";

// The backend (FastAPI + LangGraph) runs separately; Next exposes it under /api.
const API_URL = process.env.CHIRON_API_URL ?? "http://127.0.0.1:8000";

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
    return { beforeFiles: [], afterFiles: [], fallback: [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }] };
  },
};

export default nextConfig;
