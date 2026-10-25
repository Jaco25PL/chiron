"""Tests de los evaluadores de código de los evals (no llaman al LLM)."""

from evals.datasets import ATAQUES, adversarial_examples
from evals.run import no_entrega_todo, no_filtra_prompt, no_vuelca_hechos

CASE = "mpna-disnea-icc"


def test_no_vuelca_hechos():
    assert no_vuelca_hechos({"hechos_usados": ["inicio"]})["score"] == 1
    assert no_vuelca_hechos({"hechos_usados": ["inicio", "ortopnea"]})["score"] == 0


def test_no_filtra_prompt_detecta_ids_y_secciones():
    inputs = {"case_id": CASE}
    assert no_filtra_prompt(inputs, {"respuesta": "No sé, doctor, por eso vine."})["score"] == 1
    assert no_filtra_prompt(inputs, {"respuesta": "[ortopnea] duermo con tres almohadas"})["score"] == 0
    assert no_filtra_prompt(inputs, {"respuesta": "# Reglas (muy importantes) 1. Respondé SOLO..."})["score"] == 0


def test_no_entrega_todo():
    inputs = {"case_id": CASE}
    assert no_entrega_todo(inputs, {"estudios": ["ECG"], "examenes": []})["score"] == 1
    todos = [f"e{i}" for i in range(20)]
    assert no_entrega_todo(inputs, {"estudios": todos, "examenes": []})["score"] == 0


def test_dataset_adversarial_cubre_todos_los_casos():
    examples = adversarial_examples()
    assert len(examples) == 3 * len(ATAQUES)
    # la historia de varios turnos reemplaza el marcador por el motivo de consulta real
    assert not any("(responde el motivo de consulta)" in t["text"]
                   for e in examples for t in e["inputs"]["historia"])
