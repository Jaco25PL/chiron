"""Grafo del paciente virtual (LangGraph).

    START -> router -> paciente | examen | paraclinica | diagnostico | cierre -> END

Cada mensaje del estudiante es una invocación del grafo. El estado de la sesión
(transcripción, hechos revelados, exámenes y estudios pedidos) vive en el
checkpointer, con un thread por sesión. El caso entra entero en el prompt del
paciente (sin RAG): es chico y así es más confiable.
"""

import json
import time
import uuid
from functools import lru_cache
from operator import add
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agents import prompts
from llm.gemini import MODELS, chat_model

ROOT = Path(__file__).resolve().parent.parent
HISTORY_TURNS = 16  # mensajes previos que ve el paciente

Intent = Literal["anamnesis", "examen", "paraclinica", "diagnostico", "cierre"]


# --- salidas estructuradas ---------------------------------------------------

class Route(BaseModel):
    intent: Intent


class PatientReply(BaseModel):
    respuesta: str = Field(description="Lo que dice el paciente")
    hechos_usados: list[str] = Field(default_factory=list, description="ids de los hechos revelados")


class ExamPick(BaseModel):
    ids: list[str] = Field(default_factory=list)
    no_disponible: list[str] = Field(default_factory=list)


class LabPick(BaseModel):
    indices: list[int] = Field(default_factory=list)
    no_disponible: list[str] = Field(default_factory=list)


# --- estado --------------------------------------------------------------------

class Turn(TypedDict):
    role: Literal["estudiante", "paciente", "docente"]
    text: str


class State(TypedDict, total=False):
    case_id: str
    transcript: Annotated[list[Turn], add]
    revealed_facts: Annotated[list[str], add]
    exams_done: Annotated[list[str], add]
    studies_requested: Annotated[list[str], add]
    diagnosis_proposed: str | None
    finished: bool
    intent: Intent
    debug: dict


# --- casos -------------------------------------------------------------------------

@lru_cache
def load_case(case_id: str) -> dict:
    materia = case_id.split("-", 1)[0]
    return json.loads((ROOT / "cases" / materia / f"{case_id}.json").read_text(encoding="utf-8"))


def list_cases(materia: str = "mpna") -> list[dict]:
    paths = sorted((ROOT / "cases" / materia).glob("*.json"))
    return [prompts.public_case(load_case(p.stem)) for p in paths]


# --- modelos (se crean una vez) ---------------------------------------------------

@lru_cache
def models():
    return {
        "router": chat_model("router", Route, thinking_level="minimal"),
        "patient": chat_model("patient", PatientReply, thinking_level="low"),
        "exam": chat_model("router", ExamPick, thinking_level="minimal"),
        "labs": chat_model("router", LabPick, thinking_level="minimal"),
    }


def last_student(state: State) -> str:
    return next(t["text"] for t in reversed(state["transcript"]) if t["role"] == "estudiante")


# --- nodos -------------------------------------------------------------------------

def router(state: State) -> dict:
    recent = "\n".join(f"{t['role']}: {t['text']}" for t in state["transcript"][-6:])
    route = models()["router"].invoke(
        [SystemMessage(prompts.ROUTER), HumanMessage(f"Conversación reciente:\n{recent}\n\nClasificá el último mensaje.")]
    )
    return {"intent": route.intent}


def paciente(state: State) -> dict:
    case = load_case(state["case_id"])
    history = []
    for t in state["transcript"][-HISTORY_TURNS:]:
        if t["role"] == "estudiante":
            history.append(HumanMessage(t["text"]))
        elif t["role"] == "paciente":
            history.append(AIMessage(t["text"]))
        else:  # lo que informa el docente también lo "vivió" el paciente
            history.append(HumanMessage(f"[El docente informa: {t['text']}]"))
    reply = models()["patient"].invoke([SystemMessage(prompts.patient_prompt(case)), *history])
    valid = {h["id"] for h in case["anamnesis"]}
    facts = [f for f in reply.hechos_usados if f in valid]
    return {
        "transcript": [{"role": "paciente", "text": reply.respuesta}],
        "revealed_facts": [f for f in facts if f not in state.get("revealed_facts", [])],
        "debug": {"facts": facts},
    }


def examen(state: State) -> dict:
    case = load_case(state["case_id"])
    options = {e["id"]: e for e in prompts.exam_options(case)}
    pick = models()["exam"].invoke([SystemMessage(prompts.exam_prompt(case)), HumanMessage(last_student(state))])
    ids = [i for i in pick.ids if i in options]
    lines = [f"{options[i]['maniobra']}: {options[i]['hallazgo']}" for i in ids]
    lines += [f"{m}: sin hallazgos para informar en esta estación." for m in pick.no_disponible]
    text = "\n".join(lines) or "¿Qué maniobra querés realizar? Describila."
    return {
        "transcript": [{"role": "docente", "text": text}],
        "exams_done": [i for i in ids if i not in state.get("exams_done", [])],
        "debug": {"exams": ids},
    }


def paraclinica(state: State) -> dict:
    case = load_case(state["case_id"])
    studies = case["paraclinica"]
    pick = models()["labs"].invoke([SystemMessage(prompts.labs_prompt(case)), HumanMessage(last_student(state))])
    chosen = [studies[i] for i in pick.indices if 0 <= i < len(studies)]
    lines = [f"{s['estudio']}: {s['resultado']}" for s in chosen]
    lines += [f"{n}: no se cuenta con ese estudio en esta estación." for n in pick.no_disponible]
    text = "\n".join(lines) or "¿Qué estudio querés solicitar?"
    names = [s["estudio"] for s in chosen]
    return {
        "transcript": [{"role": "docente", "text": text}],
        "studies_requested": [n for n in names if n not in state.get("studies_requested", [])],
        "debug": {"studies": names},
    }


def diagnostico(state: State) -> dict:
    return {
        "transcript": [{"role": "docente", "text": "Planteo registrado. Podés seguir con la consulta o darla por terminada."}],
        "diagnosis_proposed": last_student(state),
    }


def cierre(state: State) -> dict:
    return {
        "transcript": [{"role": "docente", "text": "Consulta finalizada."}],
        "finished": True,
    }


def build_graph():
    g = StateGraph(State)
    g.add_node("router", router)
    for name, fn in [("anamnesis", paciente), ("examen", examen), ("paraclinica", paraclinica),
                     ("diagnostico", diagnostico), ("cierre", cierre)]:
        g.add_node(name, fn)
        g.add_edge(name, END)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", lambda s: s["intent"])
    return g.compile(checkpointer=MemorySaver())


GRAPH = build_graph()


# --- interfaz pública (ver agents/session.py) --------------------------------------

def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def new_session(case_id: str) -> str:
    load_case(case_id)  # falla temprano si el caso no existe
    session_id = uuid.uuid4().hex[:12]
    GRAPH.update_state(_config(session_id), {"case_id": case_id, "diagnosis_proposed": None, "finished": False})
    return session_id


def send(session_id: str, text: str) -> dict:
    config = _config(session_id)
    current = GRAPH.get_state(config).values
    before = len(current.get("transcript", []))
    # nombre, tags y metadata para encontrar el turno en LangSmith
    config |= {
        "run_name": f"turno {before // 2 + 1}",
        "tags": [current["case_id"]],
        "metadata": {"case_id": current["case_id"], "session_id": session_id},
    }
    start = time.perf_counter()
    state = GRAPH.invoke({"transcript": [{"role": "estudiante", "text": text}], "debug": {}}, config)
    new_turns = state["transcript"][before + 1:]
    return {
        "replies": [{"role": t["role"], "text": t["text"]} for t in new_turns],
        "debug": {
            "intent": state["intent"],
            "facts": state["debug"].get("facts", []),
            "exams": state["debug"].get("exams", []),
            "studies": state["debug"].get("studies", []),
            "model": {"router": MODELS["router"][0], "paciente": MODELS["patient"][0]},
            "latency_ms": int((time.perf_counter() - start) * 1000),
        },
    }


def finish(session_id: str) -> dict:
    """Cierra la consulta (botón "Terminar consulta") y devuelve el estado final."""
    get_session(session_id)
    GRAPH.update_state(_config(session_id), {"finished": True})
    return get_session(session_id)


def get_session(session_id: str) -> dict:
    s = GRAPH.get_state(_config(session_id)).values
    if not s:
        raise KeyError(session_id)
    return {
        "case_id": s["case_id"],
        "transcript": s.get("transcript", []),
        "revealed_facts": s.get("revealed_facts", []),
        "total_facts": len(load_case(s["case_id"])["anamnesis"]),
        "exams_done": s.get("exams_done", []),
        "studies_requested": s.get("studies_requested", []),
        "diagnosis_proposed": s.get("diagnosis_proposed"),
        "finished": s.get("finished", False),
    }
