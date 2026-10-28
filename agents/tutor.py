"""The study companion (tutor): answers the student's study questions in the middle of a consultation,
from the course material (RAG over data/ecoe/<materia>/).

It lives outside the patient graph: the patient never sees these exchanges and they aren't consultation
turns. It never receives the case (diagnosis, grilla, hidden facts), only what the student has already
seen in the conversation, so it can't give the case away. "principiante" gets the answer, "normal"
only a hint (prompts.TUTOR_NIVEL).
"""

from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents import prompts

FRAGMENTS = 5  # course chunks per question
RECENT_TURNS = 6  # consultation turns the tutor sees, for context


class TutorReply(BaseModel):
    respuesta: str = Field(description="Lo que le decís al estudiante: hablado, una o dos oraciones cortas, directo al grano.")


@lru_cache
def _model():
    from llm.gemini import chat_model

    return chat_model("tutor", TutorReply, retries=1, thinking_level="low")


def _search(materia: str, pregunta: str) -> list[dict]:
    from rag.search import search

    return search(materia, pregunta, k=FRAGMENTS)


def answer(materia: str, pregunta: str, nivel: str, transcript: list[dict]) -> dict:
    """{"texto": str, "fuentes": [{"tipo", "fuente", "seccion", "pagina"}]} for the student's question."""
    fragmentos = _search(materia, pregunta)
    recientes = [t for t in transcript if t["role"] in ("estudiante", "paciente", "docente")][-RECENT_TURNS:]
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
    return {"texto": reply.respuesta.strip(), "fuentes": fuentes}
