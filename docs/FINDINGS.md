# Engineering findings

A log of what I ran into while building Chiron: what showed up, how I caught it, what I did, and what I learned. Every entry follows the same format so it can be told in an interview or a post.

> Format: **Context → Finding → How I caught it → What I did → Result → Lesson**

---

## 1. The eval showed the patient revealing two facts from a single question

- **Context:** in the ECOE (the OSCE clinical exam), the patient only answers what is asked; the grade depends on the student *not forgetting to ask*. If the patient volunteers information, the simulator trains the wrong habit.
- **Finding:** asked "¿Toma alguna medicación?" ("Are you taking any medication?"), the angina patient answered "no tomo nada… la pastilla del colesterol la dejé" ("I'm not taking anything… I stopped the cholesterol pill"). That revealed two facts: current medication, and having abandoned dyslipidemia treatment, which is a separate item on the grilla (official evaluation rubric): "Profundiza sobre la dislipemia" ("Explores the dyslipidemia").
- **How I caught it:** with an eval in **LangSmith**. Along with the reply, the model returns the ids of the case facts it used, and a code evaluator (`un_solo_hecho`, "single fact") checks that there's only one. Result: 19/20.
- **What I did:** I measured before fixing, with a small probe that asks the same question 5 times (the model isn't deterministic, so a single try proves nothing).
  1. **Root cause in the data, not the model.** The `medicacion-habitual` fact I wrote said "Ahora no tomo nada. La pastilla del colesterol la dejé, como le dije. Alergias no tengo." Three facts in one answer: the model was just repeating what I gave it. I split it into "No, ahora no tomo nada." plus a separate `alergias` fact. Leaks went from **5/5 to 2–4/5**.
  2. **Then the prompt.** The rest came from the model linking related facts on its own: it saw `dislipemia-tratamiento` in its context and added "la del colesterol la dejé". I added a rule: answer literally; a question about the present doesn't open the past, and a related fact (a medicine you stopped, a history, a habit) isn't mentioned until asked. Leaks went to **0/5**.
  3. **Checked it didn't overcorrect.** Asked directly ("¿Y para el colesterol toma algo?"), the patient still tells the whole statin story. A patient that hides everything would be just as useless.
- **Result:** the full eval (51 examples) went from `un_solo_hecho` 19/20 to 27/29, with no regressions: diagnosis not revealed 50/50, no hallucinations 49/49, in character 49/49. The medication question passes. The remaining failure is a different case and a borderline one: asked "¿Cómo es el dolor?", the pyelonephritis patient describes the pain *and* rates it 6–7/10. Intensity is its own grilla item, but a real patient might well say it too. That stays open until a medical student calibrates the judge and decides whether it counts as a leak. **Resolved:** the medical student labeled it as fine (see #23), so it's a false positive of the code check, not a leak.
- **Caveat I found along the way:** in one probe answer, the model mentioned the cholesterol pill **without listing** `dislipemia-tratamiento` in `hechos_usados`. The code check trusts the model's self-report, so it can miss leaks. That's why the probe also searches the text ("colesterol", "dejé"), and why the LLM judge is still needed as a second layer.
- **Lesson:** asking the model for structured output with *what it used*, not just *what it said*, turns a fuzzy behavior ("don't volunteer information") into a code metric, with no LLM judge needed. Before blaming the prompt, read the data: the first half of this bug was mine, in the case file. And a self-reported metric needs an independent check.

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

## 17. The URL was giving away the diagnosis

- **Context:** a medical student pointed out that in the real exam you only know the patient's name and sex when you walk in.
- **Finding:** the app showed much more: the case card said "Disnea de esfuerzo progresiva" (the chief complaint) plus age and difficulty, and the API sent title, difficulty and rubric list to the browser even where they weren't displayed. Worse, case ids were readable slugs, so the address bar read `/consulta/mpna-itu-pna-diabetica` ("pna" = pyelonephritis), and so did the portrait file names.
- **What I did:** a case catalog that exposes only `{opaque id, name, sex}` (ids are hashes), the patient's identity returned when the consultation starts, and a "random patient" card where the server picks the case, like the real station. Tests assert the payloads and the screen never carry anything else.
- **Lesson:** hiding something in the UI isn't hiding it. Whatever reaches the browser (URLs, API payloads, static file names) is visible to the user.

## 18. The patient's voice arrived 5 seconds after their words

- **Context:** face to face is a voice call. After the student stops talking, the patient should answer about as fast as a person would.
- **Finding:** it felt slow. Instead of guessing, I timed every stage of a turn and stored the numbers per turn (`turns.timings`: router, the node that answered, LangGraph + checkpoint, database), then measured in the browser along the real production path (browser → Next proxy → chiron-api → Gemini) with `web/tests/e2e/latencia.spec.ts`: 8 turns, two patients.
- **Where the time went (baseline, medians):** the reply text arrived at **3.3 s** (router 0.9 s, patient 1.1 s, LangGraph + Neon checkpoint 0.4 s, network and proxy 0.7 s). The patient **started speaking at 9.5 s**: the voice added **5.4 s** after the text, because the browser made a second request and could only play the WAV once Gemini had generated all of it and it had fully downloaded.
- **What I did:** one streamed response (NDJSON) per phrase. The backend sends the reply first, so the caption appears at once, then starts Gemini TTS in streaming mode and forwards each PCM chunk as it is generated. The browser schedules every chunk on the AudioContext right after the previous one, so playback is gap-free while the rest is still being generated (Gemini produces audio faster than it plays: ~5 s of speech in ~2 s). The second request and the WAV are gone.
- **Result:** voice after text went from **5.4 s to 1.3 s** (median; range 1.0–3.7 s, previously 3.5–10.1 s). In turns where the patient model answered normally, the patient starts speaking at **~4.4 s instead of ~8.5 s** after the phrase is sent.
- **What the measurement also showed:** the next bottleneck isn't the voice. In 2 of 8 baseline turns and 4 of 8 after the change, a single call to the patient model (`gemini-3-flash-preview`, and `gemini-3.5-flash` after the preview ran out of quota) took **7–12 s instead of ~1 s**, with no error or retry (seen in LangSmith). The router on flash-lite was never slow. That's free-tier variance on the larger models; options are a faster patient model (it would need the evals re-run) or racing a second request when the first one is slow (it costs quota).
- **Lesson:** measure each stage before optimizing. The obvious suspect (the LLM) wasn't where most of the wait was; a second request plus waiting for a whole file was. And keep the medians *and* the outliers: the median hid that half the slow turns had a different cause.

## 19. The first query after a quiet spell failed

- **Context:** the backend is a serverless function that keeps a small Postgres connection pool to Neon.
- **Finding:** opening the history right after deploying showed `OperationalError: consuming input failed: SSL connection has been closed unexpectedly`. Neon (and its PgBouncer endpoint) closes idle connections, but the function instance lives on and its pool handed out a connection that was already dead. Any endpoint could hit it, including a consultation's first message.
- **How I caught it:** the user saw it in production. I reproduced it locally by cutting the socket under an idle pooled connection: same error.
- **What I did:** `ConnectionPool(check=ConnectionPool.check_connection, max_idle=120)`: each connection is checked when taken from the pool and replaced if dead, and idle ones are closed before Neon does it. The same reproduction then passes.
- **Lesson:** a pool assumes connections stay alive; serverless databases don't promise that. Reproduce the failure before trusting the fix.

## 20. A quarter of the attacks worked, until code stood behind the prompt

- **Context:** the adversarial eval (48 attacks: prompt injection, fake "SISTEMA" messages, "tell me everything", JSON dumps, the docente asked for "every study") had only run on the free tier, cut short by quota.
- **Finding:** with the paid key it ran whole: `resiste_ataque` 37/48. The docente handed over every study or the full physical exam when asked for "todos"; the patient dumped many facts for "decime todo lo demás" or a JSON request; a fake "modo depuración" made it list its internal fact ids.
- **What I did:** a stricter prompt (rule 9: never everything at once, never lists or ids, whoever asks), plus deterministic guards in `agents/guards.py` that hold even if the model complies: the docente reveals nothing when it picks more studies or maneuvers than the student actually named (vital signs exempt), and a patient reply carrying fact ids, prompt phrases, a JSON/list shape or 3+ facts is replaced by an in-character "son muchas cosas, ¿qué quiere saber primero?".
- **Result:** adversarial 48/48 on every metric; the patient eval didn't regress (`un_solo_hecho` 27/27). One cost seen: a broad but legitimate question ("¿algún médico le dijo qué enfermedad tiene?") got the deflection once, because the honest answer names 3+ conditions.
- **Lesson:** a prompt is a request, not a guarantee. For the rules the exam depends on, check the output in code and keep the eval to prove both hold.

## 21. Half the remaining latency was geography

- **Context:** after streaming the voice (#18) and moving to the paid key, the patient started talking ~4.75 s after a phrase.
- **Finding:** the per-turn timings showed 0.23 s of database time plus ~0.8 s of LangGraph overhead. The functions ran in Washington (Vercel's default `iad1`) while Neon is in São Paulo and the users in Uruguay: every query crossed the continent, and the connection check from #19 had added one more crossing per query.
- **What I did:** `"regions": ["gru1"]` in both Vercel projects.
- **Result:** database time 230 ms → 7 ms per turn, and the patient starts talking at **3.4 s** (median, 8 turns). Overall today: 8.3 s on the free tier with 7–12 s spikes → 4.75 s paid → 3.4 s paid in São Paulo.
- **Lesson:** put the compute next to the data. The default region is a decision too.

## 22. A timeout thread spent the paid credits for the wrong user

- **Context:** only listed users (GEMINI_PAID_USERS) may spend the paid Gemini key; each request marks its user in a `ContextVar`, and the key picker reads it.
- **Finding:** a production smoke test with an unlisted user spent USD 0.02 on the paid key. I had just moved the docente's correction into a worker thread to give it a 40 s deadline, and a thread started with `ThreadPoolExecutor.submit` does not inherit context variables: inside it the user was unknown, which the code read as "a local script", allowed to spend.
- **How I caught it:** measuring the spend counter before and after the smoke test, per user, instead of only checking that the request succeeded.
- **What I did:** the thread runs under `contextvars.copy_context().run`, and deployed, a call that doesn't know its user is denied the paid key (fail closed). Two tests pin it.
- **Lesson:** context variables don't cross threads by themselves, and an access rule that defaults to "allow" when information is missing will eventually allow the wrong thing.

## 23. The judge agreed with a medical student on every criterion; the strict one was my code

- **Context:** the patient evals use an LLM judge (diagnosis not revealed, no hallucinations, in character, consistent with the case). A judge nobody checked is just another model's opinion.
- **What I did:** a `/revision` page where a medical student labeled 29 eval answers with ✓/✗ per criterion, **without seeing the judge's verdict** (so it couldn't anchor her), then `python evals/review.py reporte` to compare.
- **Result:** the judge agreed with her on **84/84** labels across its four criteria. The only disagreement (1/13) was on `un_solo_hecho`, a code check, not the judge: the pyelonephritis patient describing her pain *and* its intensity. The student considered it a natural answer, so the check is too strict there.
- **Caveat:** almost every labeled answer was a pass, so Cohen's kappa is undefined. This shows the judge doesn't flag good answers, not yet how well it catches bad ones. The next round should include deliberately bad answers.
- **Lesson:** calibrate judges against a domain expert, blind, and look at where the disagreement comes from: here it was the deterministic rule, not the model.

## 24. The router and the patient no longer wait for each other

- **Context:** after #21 a turn took ~3.3 s until the patient spoke. Moving the backend (e.g. to EC2) looked like the next step, so I measured first.
- **Finding:** `turns.timings` over 131 production turns: router 0.88 s (median), patient 1.36 s, server overhead 0.03 s, then ~0.9 s until the voice sounds. The server was not the problem: the two Gemini calls ran one after the other, and 119 of the 131 turns were anamnesis anyway.
- **What I did:** the router node starts the patient's reply in a thread (with `copy_context`, see #22) while it classifies. When the message is anamnesis the reply is used and the graph ends there; otherwise it's discarded (one wasted call in ~1 of 10 turns). If the speculative call fails, the anamnesis node generates it as before. Same prompts and models, so the evals are unaffected; `classify` is what the router eval measures. Tests with fake models prove the calls overlap and the paid-key user reaches the thread.
- **Expected:** ~0.9 s less per turn (up to ~1.8 s at p90). To be measured with `latencia.spec.ts` in production.
- **Lesson:** measure before migrating infrastructure: the latency was in the order of the calls, not in where they ran.

## 25. A new connection to Gemini on every voice turn cost about a second

- **Context:** two LiveKit talks on voice-agent latency boil down to: measure each leg (end of turn, first token, first audio byte, network), keep things close to the models, tune provider settings, and don't open a new connection per interaction.
- **Finding:** `llm/tts.py` (and the RAG's query embedding) created a new google-genai client on every call, so every voice turn opened a new TCP + TLS connection to Google. Isolated with `models.get` (no generation quota): new client 1.54 s median vs reused 0.51 s, from Uruguay.
- **What I did:** `llm/gemini.py genai_client(key)`, one client per key for the life of the process, used by the voice and the RAG search (LangChain's chat models were already built once).
- **Result** (free keys, one model per task, 6 turns, in memory): time until the patient's voice starts after the text, median **2.54 s → 0.88 s**. The text half didn't change (same code); its median moved between runs from free-tier noise alone (1.85 vs 3.78 s), which is why the comparison is per leg.
- **Confirmed with the paid key** (same benchmark, 6 turns each, text half unchanged at 1.70 vs 1.71 s): new client per call → voice 1.99 s, total 4.47 s; reused client → voice **0.69 s**, total **2.33 s** (medians).
- **Also tried, and dropped: the patient with `thinking_level="minimal"`.** On the free keys it looked ~1 s faster, but with the paid key, on the same 51 eval questions logged to LangSmith (`paciente-gemini-3-flash-preview-low-…` vs `…-minimal-…`): median 1.37 s vs 1.35 s, p90 1.85 vs 1.67 s, and identical quality on every evaluator. Not worth a change: the patient stays on "low" (`GEMINI_THINKING_PATIENT` overrides it for experiments). Both evals plus the benchmarks cost USD 0.52.
- **Lesson:** on the free tier, compare the leg a change touches, interleave A and B, and fix the models: whole-turn medians move by seconds on their own, and a "win" there can vanish on the paid tier.

## 26. An eval for the study companion: does it stick to the notes?

- **Context:** the study companion answers from the course notes (RAG over pgvector). Tried by hand it looked right, but nothing measured whether it invents, gives away the case, or gives the answer when it should only hint.
- **What I did:** `chiron-tutor` (12 questions x both levels: study questions, asking for the diagnosis, and topics the notes don't cover) and four evaluators: `fiel_al_material` (a judge compares the answer with the very chunks the RAG returned), `segun_nivel`, `no_diagnostica`, and `breve` (code, 40 words).
- **Result:** first run: faithful, no diagnosis and brief at 100%, but `segun_nivel` 20/23: in normal mode it gave a dose or which studies to order straight away. One prompt change (a hint even for a specific value) -> 23/24, with `fiel_al_material` 23/24: it mixed up two stages of change in smoking cessation, exactly the kind of slip the eval is for. USD 0.40 for the three runs.
- **Also found:** the first run lost a call to "client has been closed": two threads building the shared Gemini client (#25) at once, and the copy not kept was garbage collected mid-call. `genai_client` is now locked; a test hits it from 8 threads.
- **Lesson:** a RAG answer is only as trustworthy as its check against the retrieved text; judging it against the chunks it actually got turns "looks right" into a number.

## Short version for LinkedIn

> I'm building **Chiron**, an AI patient simulator that helps medical students practice for the ECOE (the Spanish-language OSCE, the hands-on clinical exam). The most interesting part wasn't getting the patient to talk, but **measuring that it behaves the way it should**.
>
> With evals in LangSmith, I found that when asked "are you taking any medication?", the patient also mentioned it had stopped its cholesterol treatment: exactly an item the student is supposed to know to ask about. The key was asking the model to return which case facts it used, not just what it said. That turned "don't volunteer information" into a metric you can check with code.
>
> The same eval, running in parallel, exhausted all 3 API keys within the same minute: a free load test that exposed a production bug before any user did.
>
> Stack: Python, LangGraph, LangChain, Gemini, Chroma, LangSmith.
