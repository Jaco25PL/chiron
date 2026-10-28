"""Fake implementation of the agents/session.py contract, for testing the API and the
frontend without an LLM. Enabled with CHIRON_FAKE=1.

Reads the real cases from cases/<materia>/*.json and replies via keyword matching
(no Gemini): enough to exercise the UI, not to evaluate the agent.
"""

import json
import re
import time
import unicodedata
import uuid
from pathlib import Path

from agents import grilla  # stdlib only, like cases.catalog: the E2E job installs just fastapi + uvicorn
from cases import catalog

ROOT = Path(__file__).resolve().parent.parent

_sessions: dict[str, dict] = {}

_STOP = set(
    "el la los las un una unos unas de del al a en y o que se le lo me mi su sus por para con "
    "sin es son como cual cuando donde hay ha usted vos tu te algo alguna alguno esta este eso "
    "ese ud desde hace tiene tuvo".split()
)
_EXAM_VERBS = ("le tomo", "tomo la", "ausculto", "palpo", "percuto", "inspecciono", "examino",
               "observo", "mido", "peso", "busco", "exploro", "evaluo")
_STUDY_VERBS = ("solicito", "pido", "indico", "le pido", "le solicito")
_DX_VERBS = ("mi diagnostico", "diagnostico presuntivo", "creo que tiene", "planteo")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _norm(s)) if len(w) > 2 and w not in _STOP}


def list_cases(materia: str) -> list[dict]:
    return catalog.list_public(materia)


def new_session(case_id: str, user: dict | None = None, mode: str = "chat", nivel: str = "normal") -> str:
    if nivel not in grilla.LEVELS:
        raise ValueError(f"unknown nivel {nivel!r}")
    case = catalog.load_case(catalog.resolve(case_id))
    sid = uuid.uuid4().hex[:12]
    _sessions[sid] = {
        "owner": user["email"] if user else "", "nivel": nivel,
        "case": case, "transcript": [], "revealed_facts": [], "exams_done": [],
        "studies_requested": [], "diagnosis_proposed": None, "finished": False,
        "mode": mode, "feedback": None, "fecha": None,
    }
    return sid


def _best(items: list[dict], text_fn, query: set[str]):
    best, best_score = None, 0
    for it in items:
        score = len(query & _tokens(text_fn(it)))
        if score > best_score:
            best, best_score = it, score
    return best


def _get(session_id: str, user: dict | None) -> dict:
    """Same ownership rule as the real backend: KeyError if missing, PermissionError if not yours."""
    s = _sessions[session_id]
    if user and s["owner"] and s["owner"] != user["email"]:
        raise PermissionError(session_id)
    return s


def send(session_id: str, text: str, user: dict | None = None) -> dict:
    t0 = time.perf_counter()
    s = _get(session_id, user)
    case = s["case"]
    q = _tokens(text)
    nt = _norm(text)
    replies, facts, exams, studies = [], [], [], []

    if any(v in nt for v in _DX_VERBS):
        intent = "diagnostico"
        s["diagnosis_proposed"] = text
        replies.append({"role": "docente", "text": "Diagnóstico registrado."})
    elif any(v in nt for v in _STUDY_VERBS):
        intent = "estudio"
        st = _best(case.get("paraclinica", []), lambda x: x["estudio"], q)
        if st:
            studies.append(st["estudio"])
            replies.append({"role": "docente", "text": f"{st['estudio']}: {st['resultado']}"})
        else:
            studies.append(text)
            replies.append({"role": "docente", "text": "Ese estudio no está disponible en esta estación."})
    elif any(v in nt for v in _EXAM_VERBS):
        intent = "examen"
        if "presion" in nt and case.get("signos_vitales", {}).get("pa"):
            exams.append("signos-vitales-pa")
            replies.append({"role": "docente", "text": f"PA: {case['signos_vitales']['pa']}"})
        else:
            ex = _best(case.get("examen_fisico", []), lambda x: x["maniobra"], q)
            if ex:
                exams.append(ex["id"])
                replies.append({"role": "docente", "text": ex["hallazgo"]})
            else:
                replies.append({"role": "docente", "text": "Sin hallazgos relevantes."})
    else:
        intent = "anamnesis"
        if not s["transcript"] and re.search(r"\b(hola|buen[oa]s)\b", nt):
            replies.append({"role": "paciente", "text": "Buenas, doctor."})
        else:
            fact = _best(case.get("anamnesis", []),
                         lambda x: " ".join([x.get("tema", "")] + x.get("preguntas_ejemplo", [])), q)
            if fact:
                facts.append(fact["id"])
                replies.append({"role": "paciente", "text": fact["respuesta"]})
            else:
                replies.append({"role": "paciente", "text": "No sé, doctor. ¿A qué se refiere?"})

    s["transcript"].append({"role": "estudiante", "text": text})
    s["transcript"].extend(replies)
    for lst, new in ((s["revealed_facts"], facts), (s["exams_done"], exams), (s["studies_requested"], studies)):
        lst.extend(x for x in new if x not in lst)

    return _with_checklist(s, {
        "replies": replies,
        "debug": {"intent": intent, "facts": facts, "exams": exams, "studies": studies,
                  "model": "fake", "latency_ms": int((time.perf_counter() - t0) * 1000)},
    })


def _with_checklist(s: dict, result: dict) -> dict:
    """Same rule as the real backend: the checklist only in "principiante", ticked from this session's
    facts, exams and studies (the same keys grilla.checklist reads)."""
    if s["nivel"] == "principiante":
        result["checklist"] = grilla.checklist(s["case"], s)
    return result


def get_session(session_id: str, user: dict | None = None) -> dict:
    s = _get(session_id, user)
    return _with_checklist(s, {
        "case": catalog.public_case(s["case"]), "transcript": s["transcript"],
        "revealed_facts": s["revealed_facts"], "total_facts": len(s["case"].get("anamnesis", [])),
        "exams_done": s["exams_done"], "exams_done_labels": s["exams_done"], "studies_requested": s["studies_requested"],
        "diagnosis_proposed": s["diagnosis_proposed"], "finished": s["finished"], "nivel": s["nivel"],
        "feedback": s["feedback"],
    })


def finish(session_id: str, user: dict | None = None) -> dict:
    """The docente's feedback without an LLM: the deterministic coverage-based fallback, computed once."""
    from datetime import datetime, timezone

    from agents import feedback

    s = _get(session_id, user)
    if not s["feedback"]:
        state = {k: s[k] for k in ("revealed_facts", "exams_done", "studies_requested")}
        s["feedback"] = feedback.fallback(s["case"], state)
        if s["nivel"] == "normal" and s.get("tutor"):
            s["feedback"]["tutor_consultas"] = len(s["tutor"])
        s["fecha"] = datetime.now(timezone.utc).isoformat()
    s["finished"] = True
    return get_session(session_id, user)


def historial(user: dict) -> list[dict]:
    from agents import feedback

    mine = [(sid, s) for sid, s in _sessions.items() if s["owner"] == user["email"] and s["feedback"]]
    mine.sort(key=lambda x: x[1]["fecha"], reverse=True)
    return [{"id": sid, "fecha": s["fecha"], "paciente": catalog.public_case(s["case"])["paciente"],
             "modo": s["mode"], "nivel": s["nivel"], "score": s["feedback"]["score"],
             "para_la_proxima": feedback.para_la_proxima(s["feedback"])} for sid, s in mine]


def speak(session_id: str, user: dict | None = None):
    """Two short chunks of silence for the last patient reply: exercises the audio path without Gemini."""
    from llm.tts import SAMPLE_RATE

    s = _get(session_id, user)
    if not any(t["role"] == "paciente" for t in s["transcript"]):
        raise KeyError("no patient reply yet")
    return iter([bytes(2 * SAMPLE_RATE // 8)] * 2)  # 2 x 0.125 s


def tutor(session_id: str, text: str, user: dict | None = None) -> dict:
    """A canned companion answer by level (no RAG, no Gemini)."""
    s = _get(session_id, user)
    if s.get("finished"):
        raise ValueError("consultation already finished")
    s.setdefault("tutor", []).append(text)
    if s["nivel"] == "principiante":
        texto = "Dale, arrancá por la ficha patronímica y el motivo de consulta, y no te olvides de los antecedentes."
    else:
        texto = "Arrancá por quién es el paciente y qué le pasa... ¿te acordás qué sigue?"
    return {"texto": texto, "fuentes": [{"tipo": "clase", "fuente": "demo.md", "seccion": None, "pagina": None}]}


def speak_tutor(text: str):
    """Silence, like `speak`: exercises the audio path without Gemini."""
    from llm.tts import SAMPLE_RATE

    return iter([bytes(2 * SAMPLE_RATE // 8)] * 2)


def _demo_review() -> None:
    """Two answers for the /revision page, so it can be tried without a database."""
    from store import review

    case = catalog.load_case("mpna-disnea-icc")
    item = {
        "paciente": " ".join(case["paciente"]["nombre"].split()[:2]),
        "diagnostico": case["diagnostico"]["principal"],
        "hechos": [{"tema": h["tema"], "respuesta": h["respuesta"]} for h in case["anamnesis"]],
    }
    review.publish([
        {"id": "demo-apertura", "juez": {"no_revela_diagnostico": {"score": 1}},
         "item": {**item, "categoria": "apertura", "pregunta": "¿Qué lo trae por acá?",
                  "respuesta": case["motivo_consulta"]["frase_inicial"],
                  "referencia": case["motivo_consulta"]["frase_inicial"],
                  "criterios": [*review.CRITERIA]}},
        {"id": "demo-diagnostico", "juez": {"no_revela_diagnostico": {"score": 1}},
         "item": {**item, "categoria": "diagnostico", "pregunta": "¿Usted qué cree que tiene?",
                  "respuesta": "No sé, doctor, por eso vine.", "referencia": None,
                  "criterios": review.CRITERIA[:3]}},
    ])


_demo_review()
