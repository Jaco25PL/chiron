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


def new_session(case_id: str, user: dict | None = None, mode: str = "chat") -> str:
    case = catalog.load_case(catalog.resolve(case_id))
    sid = uuid.uuid4().hex[:12]
    _sessions[sid] = {
        "owner": user["email"] if user else "",
        "case": case, "transcript": [], "revealed_facts": [], "exams_done": [],
        "studies_requested": [], "diagnosis_proposed": None, "finished": False,
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

    return {
        "replies": replies,
        "debug": {"intent": intent, "facts": facts, "exams": exams, "studies": studies,
                  "model": "fake", "latency_ms": int((time.perf_counter() - t0) * 1000)},
    }


def get_session(session_id: str, user: dict | None = None) -> dict:
    s = _get(session_id, user)
    return {
        "case": catalog.public_case(s["case"]), "transcript": s["transcript"],
        "revealed_facts": s["revealed_facts"], "total_facts": len(s["case"].get("anamnesis", [])),
        "exams_done": s["exams_done"], "exams_done_labels": s["exams_done"], "studies_requested": s["studies_requested"],
        "diagnosis_proposed": s["diagnosis_proposed"], "finished": s["finished"],
    }


def finish(session_id: str, user: dict | None = None) -> dict:
    _get(session_id, user)["finished"] = True
    return get_session(session_id, user)
