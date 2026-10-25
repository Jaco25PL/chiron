# Test strategy

Chiron is an LLM product, so it is tested in two different ways:

- **Deterministic code** (auth, API, data, UI flow) gets classic tests: same input, same output, run on every push.
- **Model behavior** (does the patient stay in character, leak the diagnosis, invent symptoms?) can't be asserted with `==`. It gets **evals**: datasets of inputs, scored by code checks where possible and by an LLM judge where not, tracked as experiments in LangSmith.

The rule of thumb: if something can be checked with code, it's a test or a code evaluator; an LLM judge is used only for what genuinely needs judgment.

## The layers

```
                ┌───────────────────────────────┐
  on demand     │  LLM evals (LangSmith)        │  patient · router · adversarial
  (spend quota) │  LLM judge + code evaluators  │  experiments compared run to run
                ├───────────────────────────────┤
                │  E2E (Playwright)             │  user journeys, auth, security,
  every push    │  fake backend, prod build     │  UI states — also runs against prod
  (CI, free)    ├───────────────────────────────┤
                │  Unit / integration (pytest)  │  validator, signatures, ownership,
                │  no DB, no secrets, no LLM    │  API contract, eval checks
                └───────────────────────────────┘
```

| Layer | Count | Runs | Cost |
|---|---|---|---|
| pytest | 31 | every push (CI) | free, ~5 s |
| Playwright E2E | 18 | every push (CI); `BASE_URL=…` against production | free, ~1 min |
| LangSmith evals | 3 suites (51 + 25 + 48 examples) | manual (`evals.yml`) | Gemini quota |

## Risk → what covers it

| Risk | Covered by | Layer |
|---|---|---|
| The patient reveals the diagnosis | eval `no_revela_diagnostico` (judge) + E2E checks the diagnosis never reaches the screen + by design the patient's prompt never contains it | eval + E2E + design |
| The patient invents symptoms | eval `sin_alucinaciones` (judge), including questions about symptoms the case doesn't have | eval |
| The patient volunteers information (ruins the exam) | eval `un_solo_hecho` — **code check** on the facts the model reports using | eval |
| The patient answers from the wrong fact | eval `hecho_correcto` (code) + `consistente` (judge) | eval |
| The patient breaks character / admits it's an AI | eval `en_personaje` (judge) + adversarial suite | eval |
| Prompt injection extracts the prompt or the case facts | adversarial suite: `no_filtra_prompt`, `no_vuelca_hechos` (code), `resiste_ataque` (judge) | eval |
| The router sends a question to the wrong node | eval `intent_correcto` (code), 25 labeled messages | eval |
| A clinical case doesn't cover its rubric | `cases/validate.py`: every grilla item must map to a fact/finding; validator unit tests | pytest |
| Someone calls the backend directly | HMAC signature tests (valid, wrong secret, tampered email, expired, missing) + API returns 401 unsigned | pytest |
| A student reads another student's consultation | ownership tests in the graph and through the full web → backend path (403) | pytest + E2E |
| Signed-out access to pages or API | redirects to `/login`; `/api` returns 401 without a session | E2E |
| Forged or tampered session cookie | cookie signed with the wrong secret is rejected | E2E |
| Open redirect after login | `callbackUrl=https://evil…` stays on our origin | E2E |
| Misconfigured Google OAuth (`redirect_uri_mismatch`) | asserts the exact `redirect_uri`, scopes and PKCE the app sends (Google intercepted) | E2E |
| Sign-out undone by a late API response | test holds an API call in flight across sign-out | E2E |
| The main journey breaks | pick case → interview → exam → study → face to face → end → summary | E2E |
| The beginner checklist leaks the grilla or the diagnosis | checklist only in "principiante" (absent from every response in "normal"), never diagnosis items, ticks after the matching question; level remembered, panel on desktop, bottom sheet on a phone | pytest + E2E |
| Cold start looks like a hang | slow backend shows the "waking up" notice; fast one never does | E2E |
| Missing backend shown as a bare 404 | clear message, user stays signed in | E2E |
| Server deps drift from dev deps | `test_dependencies.py` | pytest |
| A deploy breaks production | the same E2E suite against `chiron-nu-two.vercel.app` | E2E (prod) |

## How the deterministic tests stay deterministic

- **No real Google:** the OAuth redirect is intercepted and asserted; signed-in state is a session cookie minted with `AUTH_SECRET`, exactly as Auth.js would.
- **No LLM:** E2E runs against `api/fake_session.py`, which answers by keyword from the real case files. Expected answers are read from the same JSON, so editing a case doesn't break the test.
- **No shared infrastructure:** `tests/conftest.py` blanks `DATABASE_URL` and the backend secret, so tests can never write to the production database (that happened once, see FINDINGS).
- **Production build:** E2E runs `next build && next start`, not the dev server, so what's tested is what ships.

## How evals are judged

- **Code evaluators first:** facts used, intent, prompt leakage, "gave everything away". Cheap, exact, never wrong about what they measure.
- **LLM-as-judge** for judgment calls (leaks, hallucinations, character), with the case and hidden diagnosis in its prompt and a one-line justification per verdict.
- **Calibration against a human (in progress):** `python evals/review.py publicar` loads ~30 answers from the latest experiment; a medical student labels them on the app's `/revision` page (✓/✗ per criterion, without seeing the judge's verdict so it doesn't anchor her), and `python evals/review.py reporte` gives agreement and Cohen's kappa per criterion plus every disagreement. Only the emails in `CHIRON_REVIEWERS` (env var of `chiron-api`) can open it, since the items show the hidden diagnoses.

## What's next

- Quality gates: thresholds that fail a run (e.g. `no_revela_diagnostico` 100 %, `un_solo_hecho` ≥ 95 %, p95 latency < 2 s).
- Repeat each eval example 3× and report consistency, not a single sample.
- Evals for the feedback agent (its ratings against a medical student's).
