# Chiron — web frontend

The student-facing UI for Chiron, the AI patient simulator for ECOE (OSCE) practice. It offers two modes over the same consultation: **Chat** and **Face to face** (video-call style, currently with an ASCII portrait as a placeholder for the avatar).

## Running it

```bash
npm install && npm run dev
```

Then open http://localhost:3000.

Requests to `/api/*` are proxied to the FastAPI backend, configured with `CHIRON_API_URL` (default `http://127.0.0.1:8000`). See the [root README](../README.md) for how to start the backend.

## Stack

- Next.js 16 (App Router)
- Tailwind CSS v4
- Motion (animations)
- vaul (bottom sheet)
- sonner (toasts)

`scripts/` holds the Python helpers that generate the ASCII portrait (`ascii_face.py`, `ascii_from_photo.py`).
