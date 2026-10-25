import glob
import json
from pathlib import Path

from agents import grilla
from cases.catalog import load_case

CASES = [Path(f).stem for f in glob.glob("cases/mpna/*.json")]


def test_every_case_item_has_a_kind_and_a_unique_id():
    for cid in CASES:
        its = grilla.items(load_case(cid))
        assert its and len({i["id"] for i in its}) == len(its)
        assert {i["kind"] for i in its} <= {"hecho", "examen", "estudio", "conducta", "plan", "diagnostico", "global"}


def test_items_are_covered_by_their_evidence():
    case = load_case("mpna-dolor-toracico-angina")
    aparicion = next(i for i in grilla.items(case) if "aparicion" in i["facts"])
    assert aparicion["id"] not in grilla.covered(case, {})
    assert aparicion["id"] in grilla.covered(case, {"revealed_facts": ["aparicion"]})


def test_checklist_never_shows_the_diagnosis():
    for cid in CASES:
        case = load_case(cid)
        lista = grilla.checklist(case, {})
        assert lista and not any(x["hecho"] for x in lista)
        texto = json.dumps(lista, ensure_ascii=False).lower()
        for key in case["diagnostico"].get("grilla_items", []):
            assert key.split("::", 1)[1].lower() not in texto
        assert {x["tipo"] for x in lista} <= set(grilla.CHECKLIST_KINDS)
