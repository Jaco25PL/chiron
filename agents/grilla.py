"""The case's grilla items and which ones the student has covered.

Shared by the feedback (the score) and the beginner mode (the checklist). Deterministic: the case
links each fact, maneuver and study to the grilla items it answers (`grilla_items`, see
cases/SPEC.md), so an item counts as covered when its evidence shows up in the consultation: a fact
the patient revealed, a finding the docente reported, a study the student ordered.

Kinds of item:
    hecho        answered by an anamnesis fact (ask the patient)
    examen       answered by a physical exam finding
    estudio      answered by a study (paraclínica)
    conducta     the student's conduct: greeting, explaining, asking permission, positioning
    plan         the expected plan (treatment, referral)
    diagnostico  the diagnostic reasoning: names the diagnosis, never shown before the end
    global       "Rendimiento global": the examiner's overall impression, not an item to tick
"""

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# what the beginner checklist may show: items with evidence the app can see, never the diagnosis
CHECKLIST_KINDS = ("hecho", "examen", "estudio")

# difficulty levels: same patient; "principiante" also shows the checklist during the consultation
LEVELS = ("normal", "principiante")


@lru_cache
def _grilla(materia: str, grilla_id: str) -> dict:
    path = ROOT / "data" / "ecoe" / materia / "grillas" / f"{grilla_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def item_id(key: str) -> str:
    """Short stable id for "<grilla_id>::<text>" (the text is long and has accents)."""
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def items(case: dict) -> list[dict]:
    """Every item of the case's grillas, in grilla order, deduplicated by text (several grillas repeat
    "Saluda y se presenta"): [{id, grilla, texto, kind, facts, exams, studies}]."""
    links: dict[str, dict] = {}

    def link(section: str, field: str, ident_key: str):
        for x in case.get(section, []):
            for key in x.get("grilla_items", []):
                links.setdefault(key, {"facts": [], "exams": [], "studies": []})[field].append(x[ident_key])

    link("anamnesis", "facts", "id")
    link("examen_fisico", "exams", "id")
    link("paraclinica", "studies", "estudio")
    plan = {k for x in case.get("conducta_esperada", []) for k in x.get("grilla_items", [])}
    diagnostico = set(case.get("diagnostico", {}).get("grilla_items", []))

    out, seen = [], set()
    for gid in case["grillas"]:
        g = _grilla(case["materia"], gid)
        for section in g["secciones"]:
            for texto in section["items"]:
                key = f"{gid}::{texto}"
                if _norm(texto) in seen:
                    continue
                seen.add(_norm(texto))
                ev = links.get(key, {"facts": [], "exams": [], "studies": []})
                if key in diagnostico:
                    kind = "diagnostico"
                elif key in plan:
                    kind = "plan"
                elif ev["facts"]:
                    kind = "hecho"
                elif ev["exams"]:
                    kind = "examen"
                elif ev["studies"]:
                    kind = "estudio"
                elif re.search(r"(rendimiento|desempeno) global", _norm(texto)):
                    kind = "global"
                else:
                    kind = "conducta"
                out.append({"id": item_id(key), "grilla": gid, "texto": texto, "kind": kind, **ev})
    return out


def covered(case: dict, state: dict) -> set[str]:
    """Ids of the items whose evidence is already in the consultation (any one piece is enough)."""
    facts = set(state.get("revealed_facts", []))
    exams = set(state.get("exams_done", []))
    studies = set(state.get("studies_requested", []))
    return {
        it["id"] for it in items(case)
        if facts & set(it["facts"]) or exams & set(it["exams"]) or studies & set(it["studies"])
    }


def not_indicated(case: dict) -> set[str]:
    """Study items earned by NOT ordering (e.g. "No es necesaria PC imagenológica"): every study they
    link to is marked as not indicated in the case."""
    indicated = {p["estudio"]: p.get("indicado", True) for p in case.get("paraclinica", [])}
    return {it["id"] for it in items(case)
            if it["kind"] == "estudio" and all(indicated.get(s) is False for s in it["studies"])}


def checklist(case: dict, state: dict) -> list[dict]:
    """Beginner mode: what not to forget, ticked as the student covers it. Only items the app can tick
    by itself (facts, findings, studies); conduct and diagnosis items are left to the final feedback,
    and so are the studies not to order (ordering them would tick them)."""
    done = covered(case, state)
    skip = not_indicated(case)
    return [{"id": it["id"], "texto": it["texto"], "tipo": it["kind"], "hecho": it["id"] in done}
            for it in items(case) if it["kind"] in CHECKLIST_KINDS and it["id"] not in skip]
