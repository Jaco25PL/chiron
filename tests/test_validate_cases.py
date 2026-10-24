import copy
import json
from pathlib import Path

import pytest

from cases.validate import ROOT, grilla_items, load_grilla, validate

CASES = sorted((ROOT / "cases").glob("*/*.json"))


def minimal_case(grilla_id: str = "02-disnea") -> dict:
    """Caso mínimo que cubre todos los ítems de la grilla con un hecho por ítem."""
    grilla = load_grilla("mpna", grilla_id)
    return {
        "id": "mpna-test",
        "materia": "mpna",
        "titulo": "Caso de prueba",
        "grillas": [grilla_id],
        "dificultad": "basico",
        "paciente": {k: "x" for k in [
            "nombre", "edad", "sexo", "procedencia", "domicilio", "ocupacion", "convivencia",
            "escolaridad", "estado_civil", "prestador", "medico_referencia",
        ]},
        "personalidad": {"tipo": "reservado", "descripcion": "x", "forma_de_hablar": "x"},
        "motivo_consulta": {"frase_inicial": "Me falta el aire"},
        "anamnesis": [
            {"id": f"h{i}", "tema": "x", "respuesta": "x", "grilla_items": [ref]}
            for i, ref in enumerate(grilla_items(grilla))
        ],
        "signos_vitales": {},
        "examen_fisico": [],
        "paraclinica": [],
        "diagnostico": {"principal": "insuficiencia cardíaca", "diferenciales": [], "fundamento": "x"},
        "fuentes": [],
    }


PATH = Path("mpna-test.json")


def test_minimal_case_is_valid():
    assert validate(minimal_case(), PATH) == []


def test_missing_required_field():
    case = minimal_case()
    del case["diagnostico"]
    assert "falta 'diagnostico'" in validate(case, PATH)


def test_uncovered_item_is_reported():
    case = minimal_case()
    removed = case["anamnesis"].pop(5)["grilla_items"][0]
    assert f"ítem sin cubrir: '{removed}'" in validate(case, PATH)


def test_exempt_items_need_no_coverage():
    case = minimal_case()
    case["anamnesis"] = [e for e in case["anamnesis"] if "Saluda" not in e["grilla_items"][0]]
    assert validate(case, PATH) == []


def test_unknown_item_reference():
    case = minimal_case()
    case["anamnesis"][0]["grilla_items"] = ["02-disnea::Ítem que no existe"]
    assert any("ítem inexistente" in e for e in validate(case, PATH))


def test_patient_cannot_reveal_diagnosis():
    case = minimal_case()
    case["anamnesis"][0]["respuesta"] = "El médico me dijo que tengo insuficiencia cardíaca"
    assert "el diagnóstico principal aparece en una respuesta del paciente" in validate(case, PATH)


def test_id_must_match_filename():
    case = copy.deepcopy(minimal_case())
    case["id"] = "otro"
    assert any("no coincide" in e for e in validate(case, PATH))


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_repo_cases_are_valid(path):
    case = json.loads(path.read_text(encoding="utf-8"))
    assert validate(case, path) == []
