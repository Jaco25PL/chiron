# Chiron — Architecture

How Chiron is built today, and why. Diagrams are Mermaid (rendered by GitHub).

## System overview

```mermaid
flowchart LR
    student([Student<br/>desktop or phone])

    subgraph vercel_web["Vercel · project chiron (web/)"]
        next["Next.js 16<br/>UI: chat + face to face<br/>Auth.js (Google sign-in)"]
        proxy["/api/* route handler<br/>checks session, signs identity"]
    end

    subgraph vercel_api["Vercel · project chiron-api (repo root)"]
        fastapi["FastAPI<br/>verifies signature"]
        graph["LangGraph agent<br/>router → patient / teacher"]
    end

    neon[("Neon Postgres · São Paulo<br/>consultations, turns,<br/>LangGraph checkpoints,<br/>pgvector RAG")]
    gemini["Gemini API<br/>3 keys, model fallback"]
    google["Google OAuth"]
    langsmith["LangSmith<br/>traces + evals"]

    student --> next
    next <--> google
    next --> proxy -- "HMAC-signed request" --> fastapi --> graph
    graph <--> neon
    graph --> gemini
    graph -. traces .-> langsmith
```

Two Vercel projects deploy from the same repo on every push to `main`: the frontend (root `web/`) and the backend (repo root). The browser never calls the backend directly.

## One student message, end to end

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as Next.js (Vercel)
    participant A as FastAPI (Vercel)
    participant G as LangGraph
    participant DB as Neon
    participant L as Gemini

    B->>N: POST /api/sessions/{id}/messages "¿Desde cuándo le falta el aire?"
    N->>N: Auth.js session? (else 401)
    N->>A: same request + x-chiron-user/ts/sig (HMAC)
    A->>A: verify signature (else 401), owner check (else 403)
    A->>G: send(session, text, user)
    G->>DB: load checkpoint (consultation state)
    G->>L: router (flash-lite): "anamnesis"
    G->>L: patient (flash): answer + facts used
    G->>DB: save checkpoint + turns
    G-->>A: replies + debug (intent, facts, latency)
    A-->>N: JSON
    N-->>B: patient bubble / caption
```

Typical latency: ~1–3 s per turn on warm instances. A cold start (instance scaled to zero) adds a few seconds; the UI shows "the server is waking up" after 3.5 s.

## The agent (LangGraph)

```mermaid
flowchart TD
    start([student message]) --> router{router<br/>flash-lite}
    router -- anamnesis --> patient["patient<br/>answers in character,<br/>one fact per question"]
    router -- examen --> exam["teacher: physical exam<br/>returns the case's findings"]
    router -- paraclinica --> labs["teacher: labs / imaging<br/>returns the case's results"]
    router -- diagnostico --> dx["records the student's<br/>diagnosis / plan"]
    router -- cierre --> close["ends the consultation"]
    patient & exam & labs & dx & close --> done([reply])
```

- **The case goes whole into the patient's prompt, without RAG.** A case is small, and full context is more reliable than retrieved fragments. RAG is for the course material, which the study companion answers from (see below).
- **The patient never sees the diagnosis.** Its prompt has the patient's facts only; exam findings and lab results live in the teacher nodes. Even a successful jailbreak can't reveal what the model was never given (defense in depth).
- **Structured output everywhere:** the patient returns `{respuesta, hechos_usados}`, which turns "don't volunteer information" into a metric checked with code (see evals).
- **State per consultation:** transcript, revealed facts, exams done, studies requested, proposed diagnosis, owner. Stored by LangGraph's checkpointer: `PostgresSaver` (Neon) when `DATABASE_URL` is set, `MemorySaver` locally.

## Security

| Risk | Control |
|---|---|
| Anyone uses the app | Google sign-in (Auth.js, stateless JWT cookie); `proxy.ts` sends signed-out users to `/login` |
| Someone calls the backend directly and burns the Gemini quota | Every `/api` route requires an HMAC signature (`CHIRON_BACKEND_SECRET`) that only the Next.js server can produce; 5-minute replay window |
| A student reads another student's consultation | Each consultation stores its owner; others get 403 |
| Open redirect after login | `callbackUrl` reduced to path + query on our own origin |
| A slow API response restores a signed-out session | `/api` is excluded from the session-refreshing proxy (found by a flaky E2E test, see [FINDINGS #14](docs/FINDINGS.md)) |
| The student learns the case before the consultation | Only `{opaque id, name, sex}` ever reaches the browser (`cases/catalog.py`); ids are hashes, since readable ids like `mpna-itu-pna-diabetica` leaked the diagnosis through the URL ([FINDINGS #17](docs/FINDINGS.md)); a random-patient option picks the case on the server |
| Prompt injection / jailbreak | Adversarial eval suite (`chiron-adversarial`, 16 attacks rotating over the cases) + guards in code + the patient never receives the diagnosis |

## RAG pipeline

```mermaid
flowchart LR
    pdf["Course PDFs<br/>(notes, MSP guides,<br/>lab & imaging classes)"] --> clean["clean_pdfs.py<br/>deterministic, no LLM<br/>page markers"]
    clean --> md["Markdown"] --> chunk["chunk.py<br/>LangChain splitters<br/>+ grillas JSON"]
    chunk --> jsonl["chunks.jsonl<br/>1,340 chunks"]
    jsonl --> emb["gemini-embedding-001<br/>3,072 dims"] --> chroma[("Chroma<br/>local dev")]
    chroma -- "to_pgvector.py<br/>truncate to 768 + renormalize" --> pg[("Neon pgvector<br/>HNSW cosine")]
```

- Cleaning is rule-based on purpose, so no model rewrites medical content; a word-count diff checks what was lost (< 0.1 %).
- **768-dim Matryoshka truncation:** `gemini-embedding-001` vectors keep working when truncated and re-normalized. Top-5 overlap with the full 3,072 dims was 28/30 on a sample of queries, at a quarter of the storage and no new embedding calls.
- Each chunk keeps `fuente`, `pagina` and `seccion`, so answers can cite "MPNA notes, p. 32".
- New material only needs its new chunks embedded: `python rag/chunk.py mpna` then `python rag/to_pgvector.py mpna --missing` (4 grillas = 4 embedding calls).

## RAG at runtime: the study companion

The student can stop mid-consultation and ask a study question ("¿cómo era la anamnesis de una crisis asmática?"). The study companion (`agents/tutor.py`), shown as a pet in the corner, answers from the course material through the RAG, out loud in its own voice in the call.

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (pet)
    participant A as FastAPI
    participant T as tutor.py
    participant E as Gemini embeddings
    participant PG as Neon pgvector
    participant L as Gemini flash
    participant V as Gemini TTS

    B->>A: POST /api/sessions/{id}/tutor?voz=1 "¿cómo era la anamnesis del asma?"
    Note over B: clock paused, the patient doesn't hear it
    A->>T: question + level + turns the student already saw (never the case)
    T->>E: embed the question (768 dims)
    E-->>T: vector
    T->>PG: 5 nearest chunks (cosine, HNSW)
    PG-->>T: notes, MSP guides, grillas
    T->>L: prompt: course chunks + level rule + question
    L-->>T: 1-2 sentences ("principiante": the answer, "normal": one hint)
    T-->>A: text + sources
    A-->>B: NDJSON: the text first (bubble above the pet)
    A->>V: the text in the companion's voice
    V-->>B: PCM chunks, then the call returns to the patient
```

- **It can't give the case away:** it never receives the diagnosis, the hidden facts or the case's grilla, only the turns the student has already seen. Its exchanges live outside the transcript, so the patient never sees them and they aren't consultation turns.
- **Grounded or silent:** the prompt allows only the retrieved chunks; when they don't cover the question it says "eso no lo tengo en los apuntes" instead of inventing doses or criteria.
- **Measured:** the `chiron-tutor` eval checks each answer against the very chunks it was given (`fiel_al_material`), plus help by level, no diagnosis and brevity ([FINDINGS #26](docs/FINDINGS.md)).
- **Cost per question:** one embedding, one flash call (~USD 0.002) and the voice.

## Models and quota

| Task | Models (in fallback order) | Why |
|---|---|---|
| Patient | gemini-3-flash-preview → 3.5-flash → 3.6-flash → 3.5-flash-lite | ~1 s with `thinking_level="low"`; lite as last resort when flash quota runs out |
| Router, exam, labs | gemini-3.5-flash-lite → flash-lite-latest → 3.1-flash-lite | short classification, fastest |
| Eval judge | gemini-3.6-flash → 3.5-flash → 3.7-flash | quality over speed |
| Patient voice | gemini-3.8-flash-lite-tts → 3.8-flash-tts | lite starts speaking in ~1–3 s; side by side, flash didn't sound better |
| Embeddings | gemini-embedding-001 | |

Every option is tried with each of three API keys. A per-(model, key) circuit breaker skips combinations that answered "out of quota" until they reset, and clients are built lazily on first use (model setup went from ~20 s to 0.02 s). On the free tier the flash models allow 20 requests/day per key: roughly 6 consultations a day, which is the real bottleneck, not hosting.

## Voice (face-to-face mode)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as FastAPI
    participant G as LangGraph
    participant T as Gemini TTS
    B->>B: Web Speech API (es-UY) turns the student's speech into text
    B->>A: POST /messages?voz=1 {text}  (same graph as typing)
    A->>G: router → patient
    A-->>B: line 1: patient reply (caption)
    A->>T: that reply + voice by sex + style from the case (streamed)
    loop while Gemini generates
        T-->>A: PCM chunk (24 kHz)
        A-->>B: audio line → scheduled on the AudioContext (+ analyser for lip-sync)
    end
```

- **Why not Gemini Live**, which would be faster: it writes its own replies, so it would bypass the LangGraph patient and everything the evals measure (no diagnosis leaks, one fact per question). Here voice is only input and output; the patient's words still come from the same graph.
- **It's a call, not voice messages:** like the voice mode of ChatGPT or Claude, there are only two buttons, answer and hang up. Once answered the microphone stays open; the browser's end-of-phrase detection is the turn-taking, and talking over the patient cuts their audio. Exams and studies are asked for out loud too. When the patient's voice comes back through the speakers, phrases made of the patient's own words (while they talk or 1.5 s after) are treated as echo: they neither interrupt nor get sent.
- **Speech to text in the browser:** free, no quota, near-zero latency (Chrome, Edge, Android, Safari). Firefox has no dictation, so the call can't be answered there and the Chat mode remains.
- **Only the reply just generated is spoken**, in the same request, for the consultation's owner. There is no endpoint that takes text to speak, so it can't be used as a free TTS service. The voice (Sulafat or Schedar, chosen by ear) is picked by sex, and the style ("mujer uruguaya de 61 años, de Montevideo, acento rioplatense…") is built from the case on the server, so age never reaches the browser. The style goes in `speech_metadata.style`: put inside the text, the model read it aloud.
- **Latency:** one streamed response (NDJSON) brings the reply and then the voice in chunks as Gemini generates them, so the patient starts talking with the first chunk. It used to be a second request that waited for the whole WAV; voice after text went from 5.4 s to 1.3 s (median, measured with `web/tests/e2e/latencia.spec.ts`; see [FINDINGS #18](docs/FINDINGS.md)). Each turn's per-stage timings are stored in `turns.timings`.

## The avatar

- **VRM + three.js, no React Three Fiber:** one canvas with an imperative loop doesn't need a React renderer, and R3F added ~100 KB gzipped and pinned the React version. three + GLTFLoader + three-vrm is ~200 KB gzipped, downloaded only when face to face opens.
- **Movement is code, not animation files:** breathing (spine and chest), a sway made of sines at unrelated frequencies so it never loops visibly, blinks every 2–6 s (sometimes double), eye contact with small saccades, and small nods while talking. Nothing to license, nothing to download.
- **Mouth from the voice that's playing:** the analyser on the call's audio graph gives the loudness (mouth opening, fast attack, slower release) and the zero-crossing rate, a cheap stand-in for how "bright" the vowel is (o/u vs a vs e/i).
- **Cheap on phones:** 30 fps cap, pixel ratio ≤ 1.5, a narrow lens framed on head and shoulders, the loop pauses with the tab, and everything is disposed on unmount. The generic model (pixiv's VRM 1.0 sample: redistribution allowed, no credit) went from 10.8 to 6.1 MB by shrinking its textures inside the file with `web/scripts/slim_vrm.py`.

## Grading, beginner level and history

```mermaid
flowchart LR
    C[case JSON: facts, findings, studies<br/>each linked to grilla_items] --> G[agents/grilla.py<br/>items + kind + evidence]
    S[consultation state:<br/>revealed facts, exams, studies] --> G
    G -->|principiante only| K[checklist: ticks itself]
    G --> F[agents/feedback.py<br/>one LLM call + guardrails]
    F --> DB[(feedback table)]
    DB --> H[/api/historial → side menu/]
```

- **One source of truth for "what the student did":** the case links every fact, finding and study to the grilla items it answers, so `agents/grilla.py` knows deterministically which items are covered. Both the beginner checklist and the score use it.
- **Feedback when the consultation ends** (`finish`): one call to the judge model rates every item on the grilla scale (Excelente / Bien / Regular / No realizado) and writes what went well, what was missed and 2–3 tips, in voseo. Code then overrides it: an item with no evidence in the consultation is "No realizado" whatever the model says, and one with evidence is at least "Regular". Score = points over the gradable items (0–100). If the model fails, the student still gets a coverage-only score (`parcial`).
- **The diagnosis stays hidden even in the feedback:** cases are reused, so diagnosis and plan items show only their rating under a generic label, and any sentence naming the diagnosis is dropped by code.
- **Beginner level:** same patient; the session also returns the checklist (only for `principiante`, so in Normal the browser never receives the grilla). It leaves out conduct, plan and diagnosis items and the studies that must *not* be ordered.
- **History:** a shadcn Sheet on the home page lists every graded consultation (score, patient name, mode, level, one tip), the average of the last five against the five before, and a column chart of the scores.
- **Accent color:** chosen in the user menu (Menta, Rosa, Gris, Azul), saved in `users.acento` and rendered by the server from a cookie, so the first paint already has it.

## Deployment: why Vercel + Neon

The backend needed a host that runs Python, keeps no state in memory (or can afford to lose it), and costs nothing.

| Option | Cost | Card | Verdict |
|---|---|---|---|
| Google Cloud Run | free tier usage | billing account; in Uruguay a USD 30 prepayment | dropped: no upfront payment wanted |
| Hugging Face Spaces (Docker) | — | — | dropped: Docker Spaces now require PRO (USD 9/month) |
| Render free | USD 0 | no | viable, but 512 MB RAM and ~1 min wake-up after 15 min idle |
| **Vercel Python functions + Neon** | **USD 0** | **no** | **chosen** |

**Why it works now (it didn't on day one):**

1. **No in-memory state.** Consultations live in Neon through LangGraph's `PostgresSaver`, so a function can be cold-started or scaled out between two messages without losing anything.
2. **No long-lived connections.** Voice is two plain requests per turn: speech recognition runs in the browser, and the patient's audio is one POST that returns a WAV (see [Voice](#voice-face-to-face-mode)).
3. **Small bundle.** Runtime dependencies are ~131 MB (limit: 500 MB) once Chroma and dev tooling are left out. That's why the RAG moved to pgvector.

**How it's wired:**

```
github.com/Jaco25PL/chiron  ──push to main──┬──▶ Vercel "chiron"      root: web/   → Next.js
                                            └──▶ Vercel "chiron-api"  root: /      → FastAPI
```

- `pyproject.toml` lists only runtime dependencies and sets the FastAPI entrypoint (`api.main:app`); `requirements.txt` is the dev superset (a test keeps them in sync).
- `vercel.json` gives the function 60 s and excludes `web/` from its bundle.
- `.vercelignore` keeps dev files out. **Trap:** Vercel applies the repo-root `.vercelignore` to *both* projects; listing `web/` there wiped the frontend build ([FINDINGS #16](docs/FINDINGS.md)).
- Secrets are Vercel environment variables (Gemini keys, `DATABASE_URL`, `CHIRON_BACKEND_SECRET`, LangSmith), never in the repo.
- `Dockerfile` + `deploy/cloudrun.sh` stay as a container alternative if the project outgrows functions.

**Trade-offs accepted:** cold starts (a few seconds, with a UI notice), a 60 s per-request cap (a turn takes 1–3 s), and the Neon free tier (0.5 GB, far more than this needs).

## Testing and evals

| Layer | Tool | What it covers |
|---|---|---|
| Unit / integration | pytest (39) | case validator, eval checks, HMAC signature, consultation ownership, judge-review endpoints, API with a fake backend, dependency sync |
| E2E | Playwright (24) | full consultation, the face-to-face call (with a fake speech recognizer), the judge-review page, sign-in redirects, OAuth request shape (Google intercepted), forged cookies, open redirect, sign-out race, cold-start notice, signed calls to the real backend; runs locally and against production |
| LLM behavior | LangSmith evals | patient (diagnosis leaks, hallucinations, in character, one fact per question), router intent, adversarial attacks; LLM-as-judge + code checks |

Tests run isolated from real infrastructure (`tests/conftest.py`: no database, no secret); evals run on demand because they spend model quota.

## Repo map

```
chiron/
├── agents/        LangGraph graph, nodes, prompts, public session interface
├── api/           FastAPI app + request signature check
├── llm/           Gemini models per task, key rotation, circuit breaker
├── rag/           PDF cleaning, chunking, Chroma (dev) and pgvector search
├── store/         Postgres schema, pool, checkpointer
├── cases/         clinical cases (JSON) + spec + validator
├── data/ecoe/     processed course material, grillas, chunks (raw PDFs stay local)
├── evals/         LangSmith datasets and evaluators
├── tests/         pytest
├── web/           Next.js frontend + Playwright E2E
├── docs/          engineering findings
└── deploy/        Cloud Run alternative
```

## Not built yet

- **Feedback eval and calibration:** measure the docente's ratings against a medical student's, like the patient judge. RAG-cited tips were left out: the source names (e.g. a guideline title) would give the diagnosis away.
- **Avatar, next steps:** one VRoid Studio model per patient (age and sex of the case; ours, so no license limits), vowel lip-sync with `wlipsync` instead of loudness, and measuring FPS on a mid-range Android and an older iPhone.
- **MCP server for exam tools:** dropped for now (the exam is a graph node); revisit if the tools grow.
