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

- Video call with a virtual patient
- 2–3 fictional clinical cases
- Simulated physical exam (blood pressure, auscultation, labs)
- Final feedback against a rubric
- Quality evals for the agent

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) (tentative draft).

## Running it

You need Python 3.11, Node 20+, and Gemini keys in `.env` (`GOOGLE_API_KEY_1`, `_2`, …).

```bash
# backend: FastAPI + LangGraph (port 8000)
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn api.main:app --port 8000

# frontend: Next.js (port 3000), in another terminal
cd web && npm install && npm run dev
```

Open http://localhost:3000. There are two modes that share the same consultation: **Chat** and **Face to face** (video call; for now with a static ASCII portrait instead of the avatar).

## Live demo

Frontend: **https://chiron-nu-two.vercel.app** (Google sign-in; access limited to test users while the OAuth app is in testing). Deployed on Vercel from `main` on every push. The Python backend is not hosted yet, so the hosted demo shows the UI and login only.

## Findings

What I found while building it (evals, latency, data, bugs): [docs/FINDINGS.md](docs/FINDINGS.md).

## Design decisions

### Jev in Spanish, no real-time translation

[Jev](https://typesafe.ai/) (TypeSafe) is a model for typed decisions with calibrated probabilities, intended for the graph's router and for scoring the rubric item by item. Its documentation says English is where it performs best, so I considered translating what the student says into English before passing it on. **I ruled it out:**

- **Latency:** it adds an extra call (about 0.7 s) on every router turn, and in a video call every tenth of a second counts.
- **Errors:** translation can distort medical terms, e.g. "disnea paroxística nocturna" (paroxysmal nocturnal dyspnea) or "gravitational" edema, which is exactly what the rubric has to detect.

Instead, Jev's questions and criteria, which are fixed and written by us, can be translated once, at no real-time cost. The choice is settled by an eval that compares three variants against Gemini as judge:

1. everything in Spanish
2. criteria in English, transcript in Spanish
3. everything translated
