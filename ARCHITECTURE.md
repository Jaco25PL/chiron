# Chiron — Technical Architecture

> **Tentative draft.** This architecture is an initial proposal and may change as the project evolves.

## Stack

- **Language:** Python (backend and agents)
- **Orchestration:** LangGraph + LangChain
- **Models:** Gemini API, rotating across models by task and rate limits
- **Voice and video:** Gemini Live API for real-time conversation + an animated avatar synced to the audio
- **RAG:** vector store (Chroma or FAISS) with Gemini embeddings
- **Tools:** MCP server (FastMCP) with the physical exam tools
- **Backend:** FastAPI with WebSockets
- **Frontend:** web app using the student's camera and microphone
- **Observability and evals:** LangSmith (tracing + datasets + evaluators)
- **Testing:** pytest for logic, Playwright for the E2E flow
- **Development:** Claude Code

## The graph (LangGraph)

```
start (loads the case)
   ↓
patient ←───────────┐   answers with RAG over its case
   ↓                │
router ─────────────┤   question? → patient
   │                │   exam?     → MCP tool
   │   exam (MCP)   ┘
   ↓   finished / gave a diagnosis?
feedback                LLM-as-a-judge with the rubric
   ↓
end
```

## Session state

Active case, transcript, information already revealed, exams performed, and the diagnosis proposed by the student.

## Clinical case (structure)

Patient data, chief complaint, history of present illness, past history, medication, allergies, personality (nervous, reserved, talkative), exam findings, labs, hidden diagnosis, and key questions for the rubric.

## Using the question-and-answer dataset

- Few-shot examples in the prompt, so the patient answers naturally
- Eval dataset in LangSmith
- Basis for the feedback rubric

## Evals (the differentiator)

| Eval | What it measures |
|---|---|
| Doesn't reveal the diagnosis | The patient never says what they have |
| Consistency | Doesn't contradict its case |
| No hallucinations | Doesn't invent symptoms that aren't in the case |
| In character | Talks like a patient, not like a doctor or an AI |
| Feedback quality | The rubric catches the key questions that were missed |
| Latency | Responses are fast enough for a video call |

## Repo structure (proposed)

```
chiron/
├── cases/          fictional clinical cases (JSON)
├── data/           question-and-answer dataset
├── agents/         graph, nodes, and prompts
├── rag/            indexing and retrieval
├── mcp_server/     physical exam tools
├── api/            FastAPI + WebSockets
├── frontend/       video call UI
├── evals/          LangSmith datasets and evaluators
├── tests/          pytest + Playwright
└── README.md
```

## Steps (in order, no dates)

1. Fictional clinical cases + question-and-answer dataset
2. Patient agent in LangGraph, over chat (prompt + case RAG)
3. MCP server with the physical exam tools
4. Feedback agent with a rubric (LLM-as-a-judge)
5. Evals in LangSmith
6. Voice layer with Gemini Live
7. Video call with an avatar
8. README, demo video, and LinkedIn post

Each step leaves something that works: if the video call gets complicated, there is still a chat product.

## Success metrics

- The patient doesn't reveal the diagnosis or contradict itself (evals).
- A real student uses it and finds it useful for practice.
- The feedback catches the key questions that were missed.

## Risks and assumptions

- Video call latency that breaks the experience.
- The patient hallucinates symptoms that aren't in the case.
- Free-tier API limits.
- **Assumption:** with good context and well-built cases, a free model is enough for a believable patient.

## Differentiator

It's not "a health chatbot": it's an evaluated simulator, with metrics that prove the patient behaves as it should.
