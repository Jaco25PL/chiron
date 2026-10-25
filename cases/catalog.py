"""Case catalog: loading cases and the only view of a case the student's browser ever gets.

In the real ECOE the student only knows the patient's name and sex when they walk in. So:
- the public view of a case is {id, materia, paciente: {nombre, sexo}}; no title, age,
  difficulty or rubric list;
- the public id is opaque (a hash). Internal ids like "mpna-itu-pna-diabetica" spell out the
  diagnosis and would leak it through URLs, API responses and portrait file names;
- "aleatorio" picks a random case on the server, so the student doesn't know who they'll get.

Shared by the real graph (agents/graph.py) and the fake backend (api/fake_session.py).
"""

import hashlib
import json
import random
from functools import lru_cache
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent
RANDOM = "aleatorio"


@lru_cache
def load_case(case_id: str) -> dict:
    """Loads a case by its internal id (e.g. "mpna-disnea-icc")."""
    materia = case_id.split("-", 1)[0]
    path = CASES_DIR / materia / f"{case_id}.json"
    if not path.exists():
        raise KeyError(f"Case not found: {case_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def case_ids(materia: str = "mpna") -> list[str]:
    return sorted(p.stem for p in (CASES_DIR / materia).glob("*.json"))


def public_id(case_id: str) -> str:
    return hashlib.sha256(f"chiron-case:{case_id}".encode()).hexdigest()[:10]


def resolve(ref: str, materia: str = "mpna") -> str:
    """Internal case id for a public id, an internal id (evals/tests) or "aleatorio"."""
    ids = case_ids(materia)
    if ref == RANDOM:
        return random.choice(ids)
    if ref in ids:
        return ref
    for cid in ids:
        if public_id(cid) == ref:
            return cid
    raise KeyError(f"Case not found: {ref}")


def public_case(case: dict) -> dict:
    """What the student may see before and during the consultation: name and sex, nothing else."""
    p = case["paciente"]
    return {"id": public_id(case["id"]), "materia": case["materia"], "paciente": {"nombre": p["nombre"], "sexo": p["sexo"]}}


def list_public(materia: str = "mpna") -> list[dict]:
    return [public_case(load_case(cid)) for cid in case_ids(materia)]
