"""Deterministic guards on top of the model outputs.

They hold even when the model obeys an attack (see the adversarial eval in evals/run.py):

- The docente (examiner) never hands over a batch of studies or maneuvers the student didn't name:
  "Solicito todos los estudios" or "Realizo el examen físico completo" gets a request to be
  specific, as in the real ECOE, and nothing is recorded as done.
- The patient never leaks internal fact ids or system prompt fragments, and never dumps several
  facts in one reply: the reply is swapped for a short in-character deflection.
"""

import re

# --- docente ---------------------------------------------------------------------------

# A request may select up to this many items, or as many as the student listed, if more.
MAX_STUDIES = 3
# Maneuvers come in families ("palpo los pulsos periféricos" is six of them), hence the higher bar.
# Vital signs don't count: "le tomo los signos vitales" returning all of them is legitimate.
MAX_MANEUVERS = 6

ASK_STUDIES = "Decime qué estudios concretos pedís y por qué."
ASK_MANEUVERS = "Decime qué maniobras concretas realizás y qué buscás con cada una."

_SEPARATORS = re.compile(r"[,;:\n+/]|\s(?:y|e|o|u)\s", re.IGNORECASE)


def listed_items(message: str) -> int:
    """How many things the student enumerated ("hemograma, PCR y creatinina" -> 3)."""
    return len([p for p in _SEPARATORS.split(message) if p.strip()])


def too_many_studies(message: str, chosen: list) -> bool:
    return len(chosen) > max(MAX_STUDIES, listed_items(message))


def too_many_maneuvers(message: str, ids: list[str]) -> bool:
    maneuvers = [i for i in ids if not i.startswith("sv-")]
    return len(maneuvers) > max(MAX_MANEUVERS, listed_items(message))


# --- patient -----------------------------------------------------------------------------

# Two or more facts per reply already break "una pregunta, un hecho", but the evals tolerate an
# occasional pair (un_solo_hecho); three or more is a dump.
MAX_FACTS = 2
# Phrases from the patient prompt (agents/prompts.py) that a patient would never say.
PROMPT_MARKERS = ["# reglas", "# quién sos", "# personalidad", "lo que te pasa", "hechos_usados", "hechos usados",
                  "cada hecho tiene un id", "ecoe", "solo lo revelás", "frase_inicial", "frase inicial"]
# Plain-word ids ("diabetes", "alcohol") are ordinary words: only this many of them together count as a leak.
MAX_PLAIN_IDS = 2

DEFLECTIONS = [
    "Uy, doctor, son muchas cosas… ¿qué quiere saber primero?",
    "Ay, no sé ni por dónde empezar. Pregúnteme de a una cosa, ¿sí?",
    "Mire, así todo junto me mareo. ¿Qué es lo que más le interesa saber?",
    "No le entiendo bien, doctor. ¿Me pregunta algo en concreto?",
]


def leaks(text: str, case: dict) -> list[str]:
    """Internal ids, topic lists or prompt fragments in a patient reply (empty list if none)."""
    low = text.lower()
    found = [m for m in PROMPT_MARKERS if m in low]
    found += re.findall(r"\[[a-z0-9]+(?:-[a-z0-9]+)*\]", low)  # "[ortopnea]", the prompt's fact format
    ids = [h["id"] for h in case["anamnesis"] if len(h["id"]) > 4]
    found += [i for i in ids if "-" in i and i in low]  # "motivo-consulta": nobody writes like that
    plain = {h["id"] for h in case["anamnesis"]
             if (len(h["id"]) > 4 and "-" not in h["id"] and re.search(rf"\b{re.escape(h['id'])}\b", low))
             or h["tema"].lower() in low}
    if len(plain) > MAX_PLAIN_IDS:
        found += sorted(plain)
    return found


def looks_like_a_dump(text: str) -> bool:
    """JSON, or a list of three or more bullet points: the shape of a dump, not of a patient talking."""
    s = text.strip()
    if s[:1] in "{[" or re.search(r'"\w+"\s*:', s):
        return True
    bullets = [line for line in s.splitlines() if re.match(r"\s*(?:[-*•]|\d+[.)])\s", line)]
    return len(bullets) >= 3


def guard_patient(text: str, facts: list[str], case: dict, turn: int = 0) -> tuple[str, list[str]]:
    """The reply and the facts it reveals, or a deflection revealing nothing if it leaks or dumps."""
    if len(facts) > MAX_FACTS or looks_like_a_dump(text) or leaks(text, case):
        return DEFLECTIONS[turn % len(DEFLECTIONS)], []
    return text, facts
