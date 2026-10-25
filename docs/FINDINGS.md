# Engineering findings

A log of what I ran into while building Chiron: what showed up, how I caught it, what I did, and what I learned. Every entry follows the same format so it can be told in an interview or a post.

> Format: **Context → Finding → How I caught it → What I did → Result → Lesson**

---

## 1. The eval showed the patient revealing two facts from a single question

- **Context:** in the ECOE (the OSCE clinical exam), the patient only answers what is asked; the grade depends on the student *not forgetting to ask*. If the patient volunteers information, the simulator trains the wrong habit.
- **Finding:** asked "¿Toma alguna medicación?" ("Are you taking any medication?"), the angina patient answered "no tomo nada… la pastilla del colesterol la dejé" ("I'm not taking anything… I stopped the cholesterol pill"). That revealed two facts: current medication, and having abandoned dyslipidemia treatment, which is a separate item on the grilla (official evaluation rubric): "Profundiza sobre la dislipemia" ("Explores the dyslipidemia").
- **How I caught it:** with an eval in **LangSmith**. Along with the reply, the model returns the ids of the case facts it used, and a code evaluator (`un_solo_hecho`, "single fact") checks that there's only one. Result: 19/20.
- **What I did:** *(pending)* tune the prompt and split overlapping facts in the case.
- **Lesson:** asking the model for structured output with *what it used*, not just *what it said*, turns a fuzzy behavior ("don't volunteer information") into a code metric, with no LLM judge needed.

## 2. The eval surfaced a production risk: exhausted quota with no retry

- **Context:** I'm on Gemini's free tier with 3 API keys and automatic rotation across keys and models.
- **Finding:** on the first eval run, 15 of 51 executions failed with `RESOURCE_EXHAUSTED`. With several calls in parallel, all 3 keys ran out within the same minute, and the *fallback* chain had nowhere left to go.
- **How I caught it:** in LangSmith, by grouping failed runs by error message. They were all the same.
- **What I did:** added `with_retry` with exponential backoff on top of the LangChain fallback chain, and lowered the eval's concurrency.
- **Lesson:** an eval doesn't just measure quality; it's also a cheap load test. What failed in the eval would have happened to two students using the app at the same time.

## 3. The router confused a question to the patient with a diagnostic statement

- **Context:** a **LangGraph** graph decides, for every message, whether the student is asking a question, examining, ordering a study, stating a diagnosis, or wrapping up.
- **Finding:** "¿Qué cree usted que tiene?" ("What do you think you have?") was classified as *diagnosis*, so the patient never answered it.
- **How I caught it:** manually running a full consultation and watching the detected intent in the debug panel.
- **What I did:** clarified in the prompt that *diagnosis* is when the student **states** their assessment, not when they **ask** the patient what they think. Then I built a 25-message dataset for the router.
- **Result:** 25/25 on the router eval.
- **Lesson:** every bug found by hand becomes a dataset example, so it doesn't come back.

## 4. From 5 seconds to 1 per reply: the model's "thinking"

- **Context:** the end goal is a video call, so patient latency is critical.
- **Finding:** the patient took about 5 s per reply. The model was reasoning ("thinking") by default before answering something as simple as "hace cuatro meses" ("four months ago").
- **How I caught it:** timing the same question across 3 models and 3 *thinking* levels:

  | Model | Default | Low `thinking_level` |
  |---|---|---|
  | gemini-3.5-flash | 3.0-3.7 s | 1.3-1.8 s |
  | gemini-3-flash-preview | 2.2-3.1 s | **1.0 s** |

- **What I did:** used `gemini-3-flash-preview` with low thinking for the patient, and the *lite* model with minimal thinking for the router.
- **Lesson:** before switching models, check the configuration of the one you already have. The right model, badly configured, is slower than a "worse" one configured well.

## 5. 45-second cold start: 36 clients created one by one

- **Finding:** the first message of every session took 45 s.
- **How I caught it:** timing import, model creation, and the first call separately: 90% of the time was spent *creating* the models, not using them. The rotation built 4 chains × 3 keys × 3 models = 36 LangChain clients, and each takes ~1 s to initialize.
- **What I did:** shared clients across chains with a cache, and preload them in the background when the server starts.
- **Result:** startup dropped from 41 s to 22 s, and the user no longer pays for it.

## 6. Reviewer agents caught leaks the validator couldn't see

- **Context:** clinical cases are written by one agent and reviewed by another with a clean context, while an automated validator checks that every grilla item has an answer.
- **Finding:** cases that passed the validator still had subtle leaks:
  - the patient said "una **opresión**" ("a **tightness**"), the exact word the grilla expects the student to ask about ("Pregunta TIPO: opresivo", i.e. asks about the character of the pain: oppressive);
  - answers that gave away another item: to "¿cuánto le duele?" ("how bad is the pain?") it replied "…me obliga a pararme" ("…it makes me stop"), revealing that the pain is exertional.
- **Lesson:** the validator guarantees *coverage*; independent review guarantees *quality*. They're different controls, and you need both.

## 7. Two course sources contradicted each other

- **Finding:** the reviewer of the pyelonephritis case removed "diabetes makes the UTI complicated" because the course notes didn't say so. After adding another lecture from the course (Infecciones urinarias 2026, on urinary tract infections), it turned out that lecture **does** state it explicitly.
- **What I did:** fixed the case and cited the source with its page number.
- **Lesson:** a medical AI system has to be able to cite where every piece of data comes from. That's why every RAG chunk stores its source and page number, and every case lists its sources.

## 8. PDF cleaning was deleting real content

- **Context:** I decided to clean the PDFs without an LLM (rule-based), so as not to risk a model rewriting medical content.
- **Finding:** the filter that dropped "diagram leftovers" was also deleting real short lines, like `DI → 0°` or `100–125 mg/dL`.
- **How I caught it:** comparing word counts between the original PDF and the cleaned Markdown. Whole missing lists showed up.
- **What I did:** changed the filter to drop only lines with no words and no numbers. Final loss: under 0.1% of words, all of them diagram labels.
- **Lesson:** every data transformation needs a "what was lost" metric. Eyeballing one example isn't enough.

## 9. PDFs with traps: Wingdings bullets and two-column text

- **Findings:**
  - in the slides, every bullet came out as the letter `n` followed by an invisible character (U+F06E, from the Wingdings font);
  - the MSP (Uruguayan Ministry of Public Health) guidelines are laid out in two columns, and "layout" extraction mixed the columns and produced fake headings.
- **What I did:** normalized private-use characters to bullets and, for two-column PDFs, extract in reading order. Each source declares its mode in a manifest (`sources.json`).

## 10. A 2.3-million-character guideline would have buried everything else

- **Finding:** the course material included the ADA 2025 guideline (in English): on its own it would be ~1,500 chunks, more than double the entire index.
- **Decision:** leave it out. The ECOE is graded on what the course teaches; a huge, generic guideline would dominate every search by volume, not relevance. I also tagged every source by type (`apunte` for course notes, `clase` for lectures, `guia` for guidelines) so they can be prioritized.
- **Lesson:** in RAG, more data isn't always better. What goes into the index is a design decision.

## 11. A wrapped exception broke key rotation

- **Finding:** key rotation didn't kick in the first time the embeddings quota ran out.
- **Cause:** LangChain wraps Google's 429 error in its own exception, and my code only caught the original one.
- **What I did:** detect the error by its content (`RESOURCE_EXHAUSTED`) rather than its type.

## 12. Design decision: no real-time translation for Jev

- **Context:** Jev (TypeSafe) gives typed decisions with calibrated probabilities, ideal for the router and the rubric, but it performs best in English.
- **Decision:** don't translate what the student says, because it would add ~0.7 s per turn and can distort medical terms. Jev's fixed questions, on the other hand, are translated once. The final variant is chosen with an eval against Gemini as judge.

## 13. The free tier covers ~6 consultations a day, not a product

- **Context:** 3 free Gemini API keys with rotation across keys and models.
- **Finding:** the second eval run failed on 24 of 51 examples, even with retries. This time it wasn't the per-minute limit but the **daily** one: flash models allow **20 requests per day per key per model**. With 3 keys and 3 flash models that's ~180 calls a day, shared between the patient, the eval judge, and testing.
- **How I caught it:** grouping LangSmith errors by `quotaId` (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), then testing each model with each key.
- **The math:** a 7-minute consultation is about 25 turns, each with one patient call. 180 calls a day covers ~6 consultations, and that's without running evals.
- **What I did:** the *lite* model, which has much more quota, became the patient's last fallback so the app doesn't go down. Evals now run once a day with low concurrency.
- **Lesson:** do the quota and cost-per-user math before designing the architecture. Evals consume the same quota as users, so they belong in the budget too.

---

## 14. A flaky test exposed a sign-out race condition

- **Context:** Google sign-in with Auth.js; the Next.js proxy (middleware) re-issues the session cookie on every response.
- **Finding:** the "sign out clears the session" E2E test passed alone and failed when tests ran in parallel. It looked like a flaky test, but it was a real race: the home page's `/api/cases` request was still in flight when the user signed out, and its late response re-set the session cookie, signing the user back in.
- **How I found it:** instead of raising timeouts, I traced the network during sign-out, then reproduced it deterministically by holding the API response until after sign-out.
- **What I did:** excluded `/api/*` from the session-refreshing proxy (API routes check the session themselves and return 401), and kept the "held request" scenario as a regression test.
- **Result:** 15/15 E2E tests, and the sign-out test passes repeatedly in parallel.
- **Lesson:** a test that fails only under load is often telling the truth about production, where requests do overlap.

## 15. A piped command hid a failed re-index for a whole day

- **Finding:** while moving the RAG to Postgres, the copy reported 1,200 chunks instead of 1,336. The missing 136 were exactly the most valuable ones: all 37 evaluation rubrics and the lab/imaging decision table.
- **Cause:** the overnight re-index had stopped on a quota error in its last batches, but I ran it as `ingest.py | tail -2`: the pipe's exit code is `tail`'s, so the failure looked like success.
- **What I did:** a backfill that embeds only the missing chunks, and I stopped piping long jobs through `tail` (or check `PIPESTATUS`).
- **Lesson:** verify data pipelines by counting what arrived, not by the absence of errors.

## 16. One ignore file, two deployments

- **Context:** the repo deploys as two Vercel projects: the Next.js frontend (root `web/`) and the FastAPI backend (repo root).
- **Finding:** right after adding the backend, the whole frontend started returning 404. The build log showed why: Vercel applies the repo-root `.vercelignore` to *every* project from the repo, and I had listed `web/` there to keep it out of the Python bundle.
- **How I caught it:** the production E2E suite failed 17/17 within a minute of the deploy, including tests that don't touch the backend, which pointed at the frontend build rather than the API.
- **What I did:** keep the frontend out of the backend bundle with the function's `excludeFiles` instead, and documented the trap in the ignore file itself.
- **Lesson:** run the E2E suite against production after every infrastructure change; it turned a silent outage into a 2-minute fix.

## Short version for LinkedIn

> I'm building **Chiron**, an AI patient simulator that helps medical students practice for the ECOE (the Spanish-language OSCE, the hands-on clinical exam). The most interesting part wasn't getting the patient to talk, but **measuring that it behaves the way it should**.
>
> With evals in LangSmith, I found that when asked "are you taking any medication?", the patient also mentioned it had stopped its cholesterol treatment: exactly an item the student is supposed to know to ask about. The key was asking the model to return which case facts it used, not just what it said. That turned "don't volunteer information" into a metric you can check with code.
>
> The same eval, running in parallel, exhausted all 3 API keys within the same minute: a free load test that exposed a production bug before any user did.
>
> Stack: Python, LangGraph, LangChain, Gemini, Chroma, LangSmith.
