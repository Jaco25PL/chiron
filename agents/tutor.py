"""The study companion (tutor): answers the student's study questions in the middle of a consultation,
from the course material (RAG over data/ecoe/<materia>/).

It lives outside the patient graph: the patient never sees these exchanges and they aren't consultation
turns. It never receives the case (diagnosis, grilla, hidden facts), only what the student has already
seen in the conversation, so it can't give the case away. "principiante" gets the answer, "normal"
only a hint (prompts.TUTOR_NIVEL).
"""

import contextvars
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents import prompts

FRAGMENTS = 5  # course chunks per question
RECENT_TURNS = 6  # consultation turns the tutor sees, for context
REWRITE = True  # rewrite the question with the last turns before searching (FINDINGS #29)
REWRITE_DEADLINE = 2.5  # seconds; ~1.1 s typical with the lite model
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tutor-rewrite")


class TutorReply(BaseModel):
    respuesta: str = Field(description="Lo que le decís al estudiante: hablado, una o dos oraciones cortas, directo al grano.")


class SearchQuery(BaseModel):
    consulta: str = Field(description="La pregunta reescrita para que se entienda sola.")


@lru_cache
def _rewriter():
    from llm.gemini import chat_model

    return chat_model("router", SearchQuery, retries=0, thinking_level="minimal")


def search_query(pregunta: str, recientes: list[dict]) -> str:
    """The question to search the notes with: rewritten from the last turns ("¿cómo se llama eso?" ->
    the symptom the patient described), or as asked when there are no turns, the rewrite fails or it
    takes longer than REWRITE_DEADLINE (a slow call would hold the companion's spoken answer)."""
    if not REWRITE or not recientes:
        return pregunta
    message = [HumanMessage(prompts.consulta_prompt(recientes, pregunta))]
    # copy_context: the thread must know the user, or the paid key would be misattributed (FINDINGS #22)
    future = _pool.submit(contextvars.copy_context().run, _rewriter().invoke, message)
    try:
        return future.result(timeout=REWRITE_DEADLINE).consulta.strip() or pregunta
    except Exception:  # timeout or error: a failed rewrite must not cost the student the answer
        return pregunta


@lru_cache
def _model():
    from llm.gemini import chat_model

    return chat_model("tutor", TutorReply, retries=1, thinking_level="low")


def _search(materia: str, pregunta: str) -> list[dict]:
    from rag.search import search

    return search(materia, pregunta, k=FRAGMENTS)


def answer(materia: str, pregunta: str, nivel: str, transcript: list[dict]) -> dict:
    """{"texto": str, "fuentes": [{"tipo", "fuente", "seccion", "pagina"}]} for the student's question."""
    return answer_con_material(materia, pregunta, nivel, transcript)[0]


def answer_con_material(materia: str, pregunta: str, nivel: str, transcript: list[dict]) -> tuple[dict, list[dict]]:
    """`answer` plus the course chunks it was given (the eval checks the answer sticks to them)."""
    recientes = [t for t in transcript if t["role"] in ("estudiante", "paciente", "docente")][-RECENT_TURNS:]
    fragmentos = _search(materia, search_query(pregunta, recientes))
    reply = _model().invoke([
        SystemMessage(prompts.tutor_prompt(nivel, recientes, fragmentos)),
        HumanMessage(pregunta),
    ])
    fuentes = []
    for f in fragmentos:
        m = f["metadata"]
        ref = {"tipo": m.get("tipo"), "fuente": m.get("fuente"), "seccion": m.get("seccion"), "pagina": m.get("pagina")}
        if ref not in fuentes:
            fuentes.append(ref)
    return {"texto": reply.respuesta.strip(), "fuentes": fuentes}, fragmentos
