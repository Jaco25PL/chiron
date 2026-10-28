"""Validates the clinical cases against the spec (cases/SPEC.md).

Usage:
    python cases/validate.py                 # all cases
    python cases/validate.py cases/mpna/x.json

Checks required fields, that grilla (evaluation rubric) references exist, and that
every gradable item of the case's grillas is covered. Exits with code 1 on errors.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "id", "materia", "titulo", "grillas", "dificultad", "paciente", "personalidad",
    "motivo_consulta", "anamnesis", "signos_vitales", "examen_fisico", "paraclinica",
    "diagnostico", "fuentes",
]
PACIENTE = [
    "nombre", "edad", "sexo", "procedencia", "domicilio", "ocupacion", "convivencia",
    "escolaridad", "estado_civil", "prestador", "medico_referencia",
]
# Items that grade the student's conduct, not information from the patient.
EXEMPT = re.compile(
    r"salud|present|ficha patron|motivo de consulta$|permiso|explica al paciente|explica que realizar|"
    r"explica lo que va|posiciona|acuesta|"
    r"rendimiento global|desempeño global|realiza examen con tórax descubierto|"
    r"inspección desde la pelvis",
    re.I,
)


def load_grilla(materia: str, grilla_id: str) -> dict | None:
    path = ROOT / "data" / "ecoe" / materia / "grillas" / f"{grilla_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def grilla_items(grilla: dict) -> list[str]:
    return [f"{grilla['id']}::{item}" for s in grilla["secciones"] for item in s["items"]]


def validate(case: dict, path: Path) -> list[str]:
    errors = [f"missing '{k}'" for k in REQUIRED if k not in case]
    if errors:
        return errors

    if case["id"] != path.stem:
        errors.append(f"id '{case['id']}' does not match the file name '{path.stem}'")
    errors += [f"paciente: missing '{k}'" for k in PACIENTE if k not in case["paciente"]]
    if not case["motivo_consulta"].get("frase_inicial"):
        errors.append("motivo_consulta: missing 'frase_inicial'")
    for k in ("principal", "diferenciales", "fundamento"):
        if k not in case["diagnostico"]:
            errors.append(f"diagnostico: missing '{k}'")

    entries = (
        [("anamnesis", e, ("id", "tema", "respuesta")) for e in case["anamnesis"]]
        + [("examen_fisico", e, ("id", "maniobra", "hallazgo")) for e in case["examen_fisico"]]
        + [("paraclinica", e, ("estudio", "resultado", "indicado", "justificacion")) for e in case["paraclinica"]]
        + [("conducta_esperada", e, ("accion",)) for e in case.get("conducta_esperada", [])]
        + [("diagnostico", case["diagnostico"], ())]
    )
    for section, entry, keys in entries:
        name = entry.get("id") or entry.get("estudio") or entry.get("accion", "?")
        errors += [f"{section}/{name}: missing '{k}'" for k in keys if k not in entry]

    for e in case["paraclinica"]:
        if e.get("indicado") not in (True, False, "opcional"):
            errors.append(f"paraclinica/{e.get('estudio')}: 'indicado' must be true, false or \"opcional\"")

    ids = [e.get("id") for e in case["anamnesis"] + case["examen_fisico"]]
    errors += [f"duplicate id: '{i}'" for i in {i for i in ids if ids.count(i) > 1}]

    # the diagnosis must not appear in anything the patient says
    principal = case["diagnostico"].get("principal", "").lower()
    spoken = [case["motivo_consulta"]["frase_inicial"]] + [e.get("respuesta", "") for e in case["anamnesis"]]
    if principal and any(principal in s.lower() for s in spoken):
        errors.append("the main diagnosis appears in a patient answer")

    # grilla coverage
    valid, required = set(), set()
    for gid in case["grillas"]:
        grilla = load_grilla(case["materia"], gid)
        if grilla is None:
            errors.append(f"unknown grilla: '{gid}'")
            continue
        items = grilla_items(grilla)
        valid |= set(items)
        required |= {i for i in items if not EXEMPT.search(i.split("::", 1)[1])}

    covered = set()
    for _, entry, _ in entries:
        for ref in entry.get("grilla_items", []):
            if ref not in valid:
                errors.append(f"reference to unknown item: '{ref}'")
            covered.add(ref)
    errors += [f"uncovered item: '{i}'" for i in sorted(required - covered)]
    return errors


def main():
    paths = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / "cases").glob("*/*.json"))
    failed = 0
    for path in paths:
        case = json.loads(path.read_text(encoding="utf-8"))
        errors = validate(case, path)
        status = "OK" if not errors else f"{len(errors)} errors"
        print(f"{path.relative_to(ROOT) if path.is_absolute() else path}: {status}")
        for e in errors:
            print(f"  - {e}")
        failed += bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
