"""The docente's feedback at the end of the consultation: a rating per grilla item, a score, what went
well, what was missing and tips for next time.

One LLM call grades the transcript against the grilla (agents/grilla.py), then code guardrails keep it
honest: an item the app can check (fact, finding, study) gets no credit without evidence and at least
"Regular" with it. The feedback never names the diagnosis: cases are reused, so diagnosis and plan items
are shown by rating only, and any free-text sentence that mentions the diagnosis is dropped.

If the LLM fails (quota), a deterministic coverage-based feedback is returned with `parcial: True`.
The fake backend (api/fake_session.py) uses that same fallback, so this module only imports the
standard library and agents.grilla at load time: the LLM stack is imported inside `evaluate`.

Shape (see agents/session.py):
    {"score": int 0-100, "parcial": bool,
     "bien": [str], "falto": [str], "consejos": [str],
     "items": [{"id", "texto", "tipo", "calificacion": "Excelente" | "Bien" | "Regular" | "No realizado" | None,
                "evidencia": bool}]}
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import re
import unicodedata

from agents import grilla

log = logging.getLogger("chiron.feedback")

SCALE = ("Excelente", "Bien", "Regular", "No realizado")
POINTS = {"Excelente": 3, "Bien": 2, "Regular": 1, "No realizado": 0}
EVIDENCE_KINDS = ("hecho", "examen", "estudio")  # kinds the app can verify by itself
HIDDEN_LABELS = {"diagnostico": "Planteo diagnóstico", "plan": "Conducta / plan"}  # their text names the diagnosis
# for the rare item of another kind whose verbatim text mentions the diagnosis ("ITU alta o PNA")
GENERIC_LABELS = {"hecho": "Pregunta de la anamnesis", "examen": "Maniobra del examen físico",
                  "estudio": "Estudio paraclínico", "conducta": "Conducta", "global": "Rendimiento global"}
MAX_FALTO = 5

# Words of a diagnosis that don't give it away on their own (the patient's known history, qualifiers).
_GENERIC = set(
    "paciente probable tipo modo aguda agudo cronica cronico derecha derecho izquierda izquierdo global alta alto "
    "baja bajo diag dif diagnostico diferencial diferenciales estable esfuerzo etiologia secundaria secundario "
    "eventualmente presuntivo planteo tipica tipico reducida reducido leve moderada severa dm2 hta hipertensiva "
    "hipertensivo cardiaca cardiaco renal".split()
)
# Acronyms in the grilla stand for words the feedback could also spell out.
_EXPANSIONS = {
    "itu": ["infeccion urinaria", "infeccion del tracto urinario", "infeccion de orina"],
    "pna": ["pielonefritis"],
    "icc": ["insuficiencia cardiaca"],
    "ic": ["insuficiencia cardiaca"],
}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _words(t: str) -> list[str]:
    return re.findall(r"[^\W_]+", t)


# --- never name the diagnosis ---------------------------------------------------------------------

def forbidden_terms(case: dict) -> tuple[set[str], set[str], set[str]]:
    """What would give the diagnosis away: (word stems, exact acronyms, phrases), from the hidden
    diagnosis and the grilla's diagnosis items. Words the patient says themselves are not secret."""
    dx = case.get("diagnostico", {})
    texts = [dx.get("principal", ""), *(k.split("::", 1)[-1] for k in dx.get("grilla_items", []))]
    said = " ".join([h.get("respuesta", "") for h in case.get("anamnesis", [])]
                    + [case.get("motivo_consulta", {}).get("frase_inicial", "")])
    known = {_norm(w) for w in _words(said)}
    stems, acronyms, phrases = set(), set(), set()
    for text in texts:
        for raw in _words(text):
            w = _norm(raw)
            if w in _GENERIC or w in known:
                continue
            if sum(c.isupper() for c in raw) >= 2:  # ITU, PNA, ICC
                acronyms.add(w)
                phrases.update(_EXPANSIONS.get(w, []))
            elif len(w) >= 5:
                stems.add(w[: max(5, len(w) - 2)])  # tolerate inflections: congestiva/congestion, colico/colica
    return stems, acronyms, phrases


def reveals(text: str, terms: tuple[set[str], set[str], set[str]]) -> bool:
    stems, acronyms, phrases = terms
    norm = _norm(text)
    if any(p in norm for p in phrases):
        return True
    return any(w in acronyms or any(w.startswith(s) for s in stems) for w in _words(norm))


def scrub(texts: list[str], terms) -> list[str]:
    """Drops every sentence that names the diagnosis (and the entries left empty)."""
    out = []
    for text in texts:
        kept = [s for s in re.split(r"(?<=[.!?;])\s+", text.strip()) if s and not reveals(s, terms)]
        if kept:
            out.append(" ".join(kept))
    return out


# --- score and guardrails ---------------------------------------------------------------------------

def score(results: list[dict]) -> int:
    """0-100 over the gradable items (not `global`) that have a rating."""
    rated = [r for r in results if r["tipo"] != "global" and r["calificacion"] in POINTS]
    if not rated:
        return 0
    return round(100 * sum(POINTS[r["calificacion"]] for r in rated) / (3 * len(rated)))


def guard(kind: str, evidence: bool, rating: str | None) -> str | None:
    """No credit without evidence, and at least "Regular" with it, for the items the app can check."""
    if kind in EVIDENCE_KINDS:
        if not evidence:
            return "No realizado"
        if rating not in POINTS or rating == "No realizado":
            return "Regular"
    return rating if rating in POINTS else None


def evidence(case: dict, state: dict) -> dict[str, bool]:
    """Per item: did the consultation show what the item asks for? For the items earned by not ordering
    a study, that means the student didn't order it."""
    done = grilla.covered(case, state)
    inverse = grilla.not_indicated(case)
    return {it["id"]: (it["id"] not in done) if it["id"] in inverse else (it["id"] in done)
            for it in grilla.items(case)}


def _results(case: dict, state: dict, ratings: dict[str, str]) -> list[dict]:
    seen = evidence(case, state)
    terms = forbidden_terms(case)
    out = []
    for it in grilla.items(case):
        ok = seen[it["id"]]
        texto = HIDDEN_LABELS.get(it["kind"]) or (
            GENERIC_LABELS[it["kind"]] if reveals(it["texto"], terms) else it["texto"])
        out.append({"id": it["id"], "texto": texto, "tipo": it["kind"],
                    "calificacion": guard(it["kind"], ok, ratings.get(it["id"])), "evidencia": ok})
    return out


def fallback(case: dict, state: dict) -> dict:
    """Without the LLM: what the app can check by itself (covered -> "Bien"); conduct, plan and
    diagnosis items stay unrated and out of the score."""
    ratings = {i: "Bien" for i, ok in evidence(case, state).items() if ok}
    results = _results(case, state, ratings)
    falto = [r["texto"] for r in results if r["tipo"] in EVIDENCE_KINDS and not r["evidencia"]][:MAX_FALTO]
    bien = [r["texto"] for r in results if r["tipo"] in EVIDENCE_KINDS and r["evidencia"]][:4]
    terms = forbidden_terms(case)
    return {"score": score(results), "parcial": True, "bien": scrub(bien, terms), "falto": scrub(falto, terms),
            "consejos": [], "items": results}


def para_la_proxima(feedback: dict) -> list[str]:
    """One or two short reminders for the history list."""
    return (feedback.get("consejos") or feedback.get("falto") or [])[:2]


# --- the docente (LLM) ------------------------------------------------------------------------------

DOCENTE = """Sos docente de Medicina en el Primer Nivel de Atención y corregís una estación de ECOE (examen \
clínico objetivo estructurado) en Uruguay. Un estudiante acaba de terminar una consulta con un paciente \
simulado. Corregila contra la grilla oficial.

# Caso (lo que el paciente podía contar y lo que el examen podía mostrar)
Hechos de la anamnesis:
{hechos}

Examen físico:
{examen}

Paraclínica disponible:
{paraclinica}

Diagnóstico OCULTO (solo para que evalúes el razonamiento del estudiante): {diagnostico}
Conducta esperada:
{conducta}

# Grilla
Cada ítem: id | tipo | evidencia | texto. "evidencia: sí" significa que la app registró que el estudiante \
obtuvo ese dato, hizo esa maniobra o pidió ese estudio (en los ítems de un estudio que NO corresponde pedir, \
"sí" significa que no lo pidió); "no" significa que no lo registró.
{items}

# Consulta
Planteo diagnóstico registrado del estudiante: {planteo}
Transcripción:
{transcripcion}

# Qué tenés que devolver
- `items`: una calificación para CADA ítem de la grilla (por su id): Excelente, Bien, Regular o No realizado. \
Excelente = lo hizo completo y bien; Bien = lo hizo con alguna omisión menor; Regular = lo hizo de forma \
incompleta o desordenada; No realizado = no lo hizo. Los ítems de anamnesis, examen o paraclínica sin \
evidencia van No realizado. Calificá la conducta (saludo, presentación, explicar, pedir permiso) y el planteo \
diagnóstico y el plan según la transcripción.
- `bien`: de 2 a 4 cosas concretas que hizo bien.
- `falto`: lo más importante que le faltó, como máximo 5, de lo más a lo menos importante.
- `consejos`: 2 o 3 consejos cortos y accionables para la próxima, por ejemplo: "La próxima, preguntá por los \
factores de riesgo cardiovascular antes de pasar al examen".

Tono: docente amable pero exigente, hablándole al estudiante de vos (voseo rioplatense), frases cortas. \
Escribí cada punto dirigido a él ("preguntaste bien...", "te faltó examinar..."), no en impersonal \
("Omisión de...").
MUY IMPORTANTE: el caso se reutiliza, así que en `bien`, `falto` y `consejos` NUNCA nombres ni insinúes el \
diagnóstico, sus diferenciales ni el tratamiento específico. Hablá de lo que tenía que preguntar, examinar o \
pedir, no de qué enfermedad era. Si el planteo diagnóstico fue incorrecto o faltó, decí solo que revise su \
razonamiento diagnóstico."""


def _prompt(case: dict, state: dict) -> str:
    seen = evidence(case, state)
    lines = lambda xs: "\n".join(f"- {x}" for x in xs) or "(ninguno)"  # noqa: E731
    transcript = "\n".join(f"{t['role']}: {t['text']}" for t in state.get("transcript", []))
    return DOCENTE.format(
        hechos=lines(f"{h['tema']}: {h['respuesta']}" for h in case.get("anamnesis", [])),
        examen=lines(f"{e['maniobra']}: {e['hallazgo']}" for e in case.get("examen_fisico", [])),
        paraclinica=lines(f"{p['estudio']} ({'indicado' if p.get('indicado', True) else 'NO indicado'}): "
                          f"{p['resultado']}" for p in case.get("paraclinica", [])),
        diagnostico=case.get("diagnostico", {}).get("principal", ""),
        conducta=lines(c["accion"] for c in case.get("conducta_esperada", [])),
        items="\n".join(f"{it['id']} | {it['kind']} | evidencia: {'sí' if seen[it['id']] else 'no'} | {it['texto']}"
                        for it in grilla.items(case)),
        planteo=state.get("diagnosis_proposed") or "(ninguno)",
        transcripcion=transcript or "(la consulta quedó vacía)",
    )


def _judge():
    from typing import Literal

    from pydantic import BaseModel, Field

    from llm.gemini import chat_model

    class Calificacion(BaseModel):
        id: str
        calificacion: Literal["Excelente", "Bien", "Regular", "No realizado"]

    class Correccion(BaseModel):
        items: list[Calificacion] = Field(description="Una calificación por cada ítem de la grilla")
        bien: list[str] = Field(description="2 a 4 cosas que hizo bien")
        falto: list[str] = Field(description="Lo más importante que le faltó, máximo 5")
        consejos: list[str] = Field(description="2 o 3 consejos cortos para la próxima")

    # no backoff rounds: with every key out of quota the coverage-only correction (parcial) is better
    # than waiting past the function's 60 s limit
    return chat_model("judge", Correccion, retries=0, thinking_level="low")


DEADLINE_S = 40
_POOL = ThreadPoolExecutor(max_workers=4)


def evaluate(case: dict, state: dict) -> dict:
    """The docente's feedback on a finished consultation (see the module docstring for the shape)."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        # deadline: a slow fallback model (free tier) must not run past the function's 60 s limit
        llamada = _POOL.submit(_judge().invoke, [SystemMessage(_prompt(case, state)), HumanMessage("Corregí la consulta.")])
        out = llamada.result(timeout=DEADLINE_S)
    except Exception:  # noqa: BLE001  quota, timeout or a malformed answer: the student still gets the score
        log.exception("feedback LLM failed; returning the coverage-based fallback")
        return fallback(case, state)
    results = _results(case, state, {c.id: c.calificacion for c in out.items})
    terms = forbidden_terms(case)
    return {
        "score": score(results),
        "parcial": False,
        "bien": scrub(out.bien, terms)[:4],
        "falto": scrub(out.falto, terms)[:MAX_FALTO],
        "consejos": scrub(out.consejos, terms)[:3],
        "items": results,
    }
