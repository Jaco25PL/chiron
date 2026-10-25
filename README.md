# Chiron — Product Brief

## Name

Chiron is named after the centaur of Greek mythology who taught medicine to Asclepius, the god of medicine, and trained other great healers. He was the teacher of physicians. Chiron doesn't heal patients: it trains the people who will, just like this product.

## Problem

Health-science students need to practice clinical interviews, but practicing with real patients or actors (standardized patients) is expensive, limited, and tied to schedules. Many reach real clinical practice with little experience and no feedback.

## User

Medical or nursing students preparing for clinical interviews and practical exams, such as the ECOE (the Spanish-language name of the OSCE).

## Solution

A virtual patient on a video call. The student takes the history (anamnesis) and "examines" the patient, as in a real consultation. At the end, they get feedback on what they asked well and what they missed.

## Value proposition

Practice whenever you want, as often as you want, with varied cases and immediate feedback.

## Goals

- **Product:** practice should feel realistic and the feedback should be useful.
- **Personal:** show that I can build and test an AI system end to end.

## MVP scope

| Item | Status |
|---|---|
| 2–3 fictional clinical cases, built from the official rubrics (grillas) | ✅ 3 cases, validated + reviewed |
| Patient agent over chat (LangGraph) | ✅ live |
| Simulated physical exam and lab/imaging requests | ✅ teacher node in the graph |
| "Face to face" video-call layout | ✅ static ASCII portrait (avatar pending) |
| Quality evals for the agent (LangSmith) | ✅ patient, router, adversarial suites |
| Final feedback against the rubric | ⏳ next |
| Real-time voice + animated avatar | ⏳ later |

Out of scope for now: an MCP server for the physical exam tools. The original plan had one, but the exam is implemented as a node of the graph, which needs no extra process. MCP stays an option if the exam tools grow.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md): system overview, request flow, the graph, security, RAG, and why everything runs on Vercel + Neon at zero cost.

## Running it

You need Python 3.12+, Node 20+, and Gemini keys in `.env` (`GOOGLE_API_KEY_1`, `_2`, …). Optional: `DATABASE_URL` (Neon Postgres) to persist consultations; without it everything stays in memory.

```bash
# backend: FastAPI + LangGraph (port 8000)
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn api.main:app --port 8000

# frontend: Next.js (port 3000), in another terminal
cd web && npm install && npm run dev
```

Open http://localhost:3000. There are two modes that share the same consultation: **Chat** and **Face to face** (video call; for now with a static ASCII portrait instead of the avatar).

## Live demo

**https://chiron-nu-two.vercel.app** (Google sign-in; access limited to test users while the OAuth app is in testing). Frontend and backend both deploy on Vercel from `main` on every push; consultations are stored in Neon Postgres.

## Findings

What I found while building it (evals, latency, data, bugs): [docs/FINDINGS.md](docs/FINDINGS.md).

## Design decisions

### Jev (TypeSafe): evaluated, not adopted

[Jev](https://typesafe.ai/) returns typed decisions with calibrated probabilities, a good fit on paper for the graph's router and for scoring the rubric item by item. I evaluated it and **did not adopt it**; there is no Jev code in the repo:

- **The router doesn't need it today.** The Gemini flash-lite router scores 25/25 on its LangSmith eval, at ~1 s and free-tier cost.
- **Language risk.** Its docs say English is where it performs best. Translating the student's words in real time would add ~0.7 s per router turn and can distort exactly the medical terms the rubric must detect (e.g. "disnea paroxística nocturna", "edemas gravitacionales").

If the rubric scorer needs calibrated per-item confidence later, the plan is to translate only Jev's fixed criteria once (no real-time cost) and pick between Spanish-only, English criteria + Spanish transcript, and full translation with an eval against Gemini as judge.

### Vercel for the backend too

The backend runs on Vercel as a Python function, next to the frontend, with Neon Postgres for state and vectors. It was chosen over Cloud Run (needs a billing account and, in Uruguay, a USD 30 prepayment) and Hugging Face Spaces (Docker Spaces now require PRO). Details and trade-offs in [ARCHITECTURE.md](ARCHITECTURE.md#deployment-why-vercel--neon).
