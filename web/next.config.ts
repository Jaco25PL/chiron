import type { NextConfig } from "next";

// El backend (FastAPI + LangGraph) corre aparte; Next lo expone bajo /api.
const API_URL = process.env.CHIRON_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  devIndicators: false, // el indicador tapaba el botón del micrófono en mobile
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
  rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
