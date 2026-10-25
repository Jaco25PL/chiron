// Auth.js endpoints (/api/auth/*). As a filesystem route it takes precedence over the
// /api/* rewrite to the FastAPI backend in next.config.ts.
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
