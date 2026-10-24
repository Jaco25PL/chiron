"""Implementación falsa del contrato de agents/session.py, para probar la API y el front
sin LLM. Se activa con CHIRON_FAKE=1.

Lee los casos reales de cases/<materia>/*.json y responde con matching de palabras clave
(sin Gemini): suficiente para ejercitar la UI, no para evaluar el agente.
"""

import json
import re
import time
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "cases"

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


def _load_case(case_id: str) -> dict:
    for path in CASES_DIR.glob(f"*/{case_id}.json"):
        return json.loads(path.read_text(encoding="utf-8"))
    raise KeyError(f"Caso no encontrado: {case_id}")


def list_cases(materia: str) -> list[dict]:
    out = []
    for path in sorted((CASES_DIR / materia).glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        p = c.get("paciente", {})
        out.append({
            "id": c["id"], "materia": c["materia"], "titulo": c["titulo"],
            "dificultad": c.get("dificultad"), "grillas": c.get("grillas", []),
            "paciente": {"nombre": p.get("nombre"), "edad": p.get("edad"), "sexo": p.get("sexo")},
        })
    return out


def new_session(case_id: str) -> str:
    case = _load_case(case_id)
    sid = uuid.uuid4().hex[:12]
    _sessions[sid] = {
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


def send(session_id: str, text: str) -> dict:
    t0 = time.perf_counter()
    s = _sessions[session_id]
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


def get_session(session_id: str) -> dict:
    s = _sessions[session_id]
    return {
        "case_id": s["case"]["id"], "transcript": s["transcript"],
        "revealed_facts": s["revealed_facts"], "total_facts": len(s["case"].get("anamnesis", [])),
        "exams_done": s["exams_done"], "studies_requested": s["studies_requested"],
        "diagnosis_proposed": s["diagnosis_proposed"], "finished": s["finished"],
    }


def finish(session_id: str) -> dict:
    _sessions[session_id]["finished"] = True
    return get_session(session_id)
