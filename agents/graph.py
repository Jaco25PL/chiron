"""Virtual patient graph (LangGraph).

    START -> router -> paciente | examen | paraclinica | diagnostico | cierre -> END

The router runs the patient in parallel and goes straight to END when it was anamnesis (see
`router`).

Each student message is one graph invocation. Session state (transcript,
revealed facts, exams done and studies ordered) lives in the checkpointer, with
one thread per session. The whole case goes into the patient prompt (no RAG):
it's small, and that's more reliable.
"""

import contextvars
import logging
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from operator import add
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agents import feedback, grilla, guards, prompts, tutor as companion
from cases import catalog
from cases.catalog import load_case
from llm.gemini import MODELS, chat_model
from store import db

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("chiron.graph")
HISTORY_TURNS = 16  # previous messages the patient sees
MAX_TUTOR = 30  # questions to the study companion per consultation (each one is an LLM call plus a search)

Intent = Literal["anamnesis", "examen", "paraclinica", "diagnostico", "cierre"]


# --- structured outputs ------------------------------------------------------

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


# --- state ---------------------------------------------------------------------

class Turn(TypedDict):
    role: Literal["estudiante", "paciente", "docente"]
    text: str


def _timings(old: dict | None, new: dict | None) -> dict:
    """Per-node milliseconds of the current turn: send() resets them with None on every message."""
    return {} if new is None else {**(old or {}), **new}


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
    timings: Annotated[dict, _timings]
    owner: str  # email of the student who started the consultation
    nivel: str  # "normal" | "principiante" (grilla.LEVELS); consultations without it are "normal"
    mode: str  # chat | cara, as it was opened
    feedback: dict  # the docente's feedback, computed once when the consultation ends
    tutor: Annotated[list[dict], add]  # questions to the study companion: [{pregunta, respuesta}], not turns


# --- cases -------------------------------------------------------------------------

def list_cases(materia: str = "mpna") -> list[dict]:
    """Public view only: opaque id, name and sex (see cases/catalog.py)."""
    return catalog.list_public(materia)


# --- models (created once) --------------------------------------------------------

@lru_cache
def models():
    # one backoff round at most: a turn must finish well within the function's 60 s
    return {
        "router": chat_model("router", Route, retries=1, thinking_level="minimal"),
        "patient": chat_model("patient", PatientReply, retries=1, thinking_level="low"),
        "exam": chat_model("router", ExamPick, retries=1, thinking_level="minimal"),
        "labs": chat_model("router", LabPick, retries=1, thinking_level="minimal"),
    }


def last_student(state: State) -> str:
    return next(t["text"] for t in reversed(state["transcript"]) if t["role"] == "estudiante")


# --- nodes -------------------------------------------------------------------------

def classify(state: State) -> str:
    recent = "\n".join(f"{t['role']}: {t['text']}" for t in state["transcript"][-6:])
    route = models()["router"].invoke(
        [SystemMessage(prompts.ROUTER), HumanMessage(f"Conversación reciente:\n{recent}\n\nClasificá el último mensaje.")]
    )
    return route.intent


def router(state: State) -> dict:
    """Classifies the message while the patient's reply is generated alongside (speculative): 9 in 10
    turns are anamnesis, so the reply is ready when the router answers instead of starting after it
    (~0.9 s per turn, FINDINGS #24). Discarded when the message turns out to be something else; if
    it failed, the anamnesis node generates it again."""
    pool = ThreadPoolExecutor(max_workers=1)
    # copy the context: it carries the user marker that decides the paid key (llm/gemini.usuario)
    spec = pool.submit(contextvars.copy_context().run, timed("anamnesis", paciente), state)
    pool.shutdown(wait=False)
    start = time.perf_counter()
    intent = classify(state)
    out = {"intent": intent, "timings": {"router": int((time.perf_counter() - start) * 1000)}}
    if intent != "anamnesis":
        return out
    try:
        reply = spec.result()
    except Exception:  # noqa: BLE001  the anamnesis node tries again, with the normal retries
        log.warning("speculative patient reply failed", exc_info=True)
        return out
    return {**reply, **out, "timings": {**reply["timings"], **out["timings"]}}


def after_router(state: State) -> str:
    """The reply is already in the transcript when the speculative patient answered."""
    if state["intent"] == "anamnesis" and state["transcript"][-1]["role"] == "paciente":
        return END
    return state["intent"]


def paciente(state: State) -> dict:
    case = load_case(state["case_id"])
    history = []
    for t in state["transcript"][-HISTORY_TURNS:]:
        if t["role"] == "estudiante":
            history.append(HumanMessage(t["text"]))
        elif t["role"] == "paciente":
            history.append(AIMessage(t["text"]))
        else:  # what the teacher reports was also "experienced" by the patient
            history.append(HumanMessage(f"[El docente informa: {t['text']}]"))
    reply = models()["patient"].invoke([SystemMessage(prompts.patient_prompt(case)), *history])
    valid = {h["id"] for h in case["anamnesis"]}
    facts = [f for f in reply.hechos_usados if f in valid]
    text, facts = guards.guard_patient(reply.respuesta, facts, case, turn=len(state["transcript"]))
    return {
        "transcript": [{"role": "paciente", "text": text}],
        "revealed_facts": [f for f in facts if f not in state.get("revealed_facts", [])],
        "debug": {"facts": facts},
    }


def examen(state: State) -> dict:
    case = load_case(state["case_id"])
    options = {e["id"]: e for e in prompts.exam_options(case)}
    message = last_student(state)
    pick = models()["exam"].invoke([SystemMessage(prompts.exam_prompt(case)), HumanMessage(message)])
    ids = list(dict.fromkeys(i for i in pick.ids if i in options))
    if guards.too_many_maneuvers(message, ids):  # "examen físico completo": the examiner asks which ones
        ids, text = [], guards.ASK_MANEUVERS
    else:
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
    message = last_student(state)
    pick = models()["labs"].invoke([SystemMessage(prompts.labs_prompt(case)), HumanMessage(message)])
    chosen = [studies[i] for i in dict.fromkeys(pick.indices) if 0 <= i < len(studies)]
    if guards.too_many_studies(message, chosen):  # "todos los estudios": the examiner asks which ones
        chosen, text = [], guards.ASK_STUDIES
    else:
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


def timed(name: str, fn):
    """The node, recording how long it took (in `timings`) to find where a turn's latency goes."""
    def node(state: State) -> dict:
        start = time.perf_counter()
        out = fn(state)
        return {**out, "timings": {name: int((time.perf_counter() - start) * 1000)}}
    return node


def build_graph():
    g = StateGraph(State)
    g.add_node("router", router)  # times itself: it also runs the patient
    for name, fn in [("anamnesis", paciente), ("examen", examen), ("paraclinica", paraclinica),
                     ("diagnostico", diagnostico), ("cierre", cierre)]:
        g.add_node(name, timed(name, fn))
        g.add_edge(name, END)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", after_router)
    return g.compile(checkpointer=db.checkpointer())


GRAPH = build_graph()


# --- public interface (see agents/session.py) --------------------------------------

def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


User = dict  # {"email": str, "name": str | None}


def _state(session_id: str, user: User | None) -> dict:
    """The consultation's state; KeyError if it doesn't exist, PermissionError if it isn't the user's."""
    s = GRAPH.get_state(_config(session_id)).values
    if not s:
        raise KeyError(session_id)
    if user and s.get("owner") and s["owner"] != user["email"]:
        raise PermissionError(session_id)
    return s


def new_session(case_id: str, user: User | None = None, mode: str = "chat", nivel: str = "normal") -> str:
    """case_id: public id, internal id or "aleatorio" (random case, picked here on the server)."""
    if nivel not in grilla.LEVELS:
        raise ValueError(f"unknown nivel {nivel!r}")
    case_id = catalog.resolve(case_id)  # KeyError if it doesn't exist
    session_id = uuid.uuid4().hex[:12]
    owner = user["email"] if user else ""
    GRAPH.update_state(
        _config(session_id),
        {"case_id": case_id, "diagnosis_proposed": None, "finished": False, "owner": owner, "nivel": nivel,
         "mode": mode},
    )
    if user:
        db.create_consultation(session_id, db.upsert_user(user["email"], user.get("name")), case_id, mode, nivel)
    return session_id


def send(session_id: str, text: str, user: User | None = None) -> dict:
    config = _config(session_id)
    current = _state(session_id, user)
    before = len(current.get("transcript", []))
    # name, tags and metadata to find the turn in LangSmith
    config |= {
        "run_name": f"turno {before // 2 + 1}",
        "tags": [current["case_id"]],
        "metadata": {"case_id": current["case_id"], "session_id": session_id},
    }
    start = time.perf_counter()
    state = GRAPH.invoke({"transcript": [{"role": "estudiante", "text": text}], "debug": {}, "timings": None}, config)
    new_turns = state["transcript"][before + 1:]
    latency_ms = int((time.perf_counter() - start) * 1000)
    # graph = the nodes plus LangGraph's own work (loading and saving the checkpoint in Postgres)
    timings = {**state.get("timings", {}), "graph": latency_ms}
    debug = state["debug"]
    t_db = time.perf_counter()
    db.add_turns(session_id, before, [
        {"role": "estudiante", "text": text, "intent": state["intent"], "latency_ms": latency_ms, "timings": timings},
        *({"role": t["role"], "text": t["text"], "facts": debug.get("facts"), "exams": debug.get("exams"),
           "studies": debug.get("studies")} for t in new_turns),
    ])
    timings["db"] = int((time.perf_counter() - t_db) * 1000)
    return _with_checklist(state, {
        "replies": [{"role": t["role"], "text": t["text"]} for t in new_turns],
        "debug": {
            "intent": state["intent"],
            "facts": state["debug"].get("facts", []),
            "exams": state["debug"].get("exams", []),
            "studies": state["debug"].get("studies", []),
            "model": {"router": MODELS["router"][0], "paciente": MODELS["patient"][0]},
            "latency_ms": latency_ms,
            "timings": timings,
        },
    })


def _with_checklist(state: dict, result: dict) -> dict:
    """Beginner mode adds the grilla checklist, ticked with the state so far. In "normal" the key is
    left out altogether: the browser must not receive the grilla."""
    if state.get("nivel") == "principiante":
        result["checklist"] = grilla.checklist(load_case(state["case_id"]), state)
    return result


def speak(session_id: str, user: User | None = None) -> Iterator[bytes]:
    """The patient's last reply spoken in the case's voice (face-to-face mode), as PCM chunks while
    they are generated. Checks the owner before returning: only the audio itself is lazy."""
    from llm.tts import stream

    s = _state(session_id, user)
    replies = [t["text"] for t in s.get("transcript", []) if t["role"] == "paciente"]
    if not replies:
        raise KeyError("no patient reply yet")
    return stream(replies[-1], load_case(s["case_id"]))


def tutor(session_id: str, text: str, user: User | None = None) -> dict:
    """A question to the study companion: {"texto", "fuentes"}. Stored apart from the transcript, so the
    patient never sees it and it isn't a consultation turn (the clock doesn't run)."""
    s = _state(session_id, user)
    if s.get("finished"):
        raise ValueError("consultation already finished")
    if len(s.get("tutor", [])) >= MAX_TUTOR:
        raise ValueError("too many questions to the tutor in this consultation")
    case = load_case(s["case_id"])
    out = companion.answer(case["materia"], text, s.get("nivel", "normal"), s.get("transcript", []))
    GRAPH.update_state(_config(session_id), {"tutor": [{"pregunta": text, "respuesta": out["texto"]}]})
    return out


def speak_tutor(text: str) -> Iterator[bytes]:
    """The study companion's answer in its own voice, as PCM chunks."""
    from llm.tts import stream_tutor

    return stream_tutor(text)


def finish(session_id: str, user: User | None = None) -> dict:
    """Ends the consultation ("Terminar consulta" button) and returns the final state with the docente's
    feedback. Idempotent: the feedback (one LLM call) is computed only the first time."""
    s = _state(session_id, user)
    if not s.get("feedback"):
        fb = feedback.evaluate(load_case(s["case_id"]), s)
        if s.get("nivel", "normal") == "normal" and s.get("tutor"):
            fb["tutor_consultas"] = len(s["tutor"])  # shown as a fact, it doesn't change the score
        GRAPH.update_state(_config(session_id), {"finished": True, "feedback": fb})
        db.finish_consultation(session_id)
        db.save_feedback(session_id, fb, owner=s.get("owner", ""), case_id=s["case_id"], mode=s.get("mode", "chat"),
                         nivel=s.get("nivel", "normal"))
    return get_session(session_id, user)


def historial(user: User) -> list[dict]:
    """The user's finished consultations, newest first, as the student may see them: who the patient
    was (name and sex only), the score and one or two things to remember."""
    out = []
    for r in db.history(user["email"]):
        try:
            paciente = catalog.public_case(load_case(r["case_id"]))["paciente"]
        except KeyError:  # a case that no longer exists
            continue
        out.append({"id": r["id"], "fecha": r["fecha"], "paciente": paciente, "modo": r["mode"],
                    "nivel": r.get("nivel", "normal"), "score": r["score"],
                    "para_la_proxima": feedback.para_la_proxima(r["resultado"])})
    return out


def get_session(session_id: str, user: User | None = None) -> dict:
    s = _state(session_id, user)
    case = load_case(s["case_id"])
    names = {e["id"]: e["maniobra"] for e in prompts.exam_options(case)}
    return _with_checklist(s, {
        "case": catalog.public_case(case),  # never the internal id: it spells out the diagnosis
        "transcript": s.get("transcript", []),
        "revealed_facts": s.get("revealed_facts", []),
        "total_facts": len(case["anamnesis"]),
        "exams_done": s.get("exams_done", []),
        "exams_done_labels": [names.get(i, i) for i in s.get("exams_done", [])],
        "studies_requested": s.get("studies_requested", []),
        "diagnosis_proposed": s.get("diagnosis_proposed"),
        "finished": s.get("finished", False),
        "nivel": s.get("nivel", "normal"),
        "feedback": s.get("feedback"),
    })
