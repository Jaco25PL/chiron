"""The study companion (agents/tutor.py): fake model and search, no Gemini, no database."""

from types import SimpleNamespace

import pytest

from agents import graph, prompts, tutor
from cases.catalog import load_case

CASE = "mpna-crisis-asmatica"
USER = {"email": "tutor@example.com", "name": None}
FRAGMENTO = {"texto": "La anamnesis empieza por la ficha patronímica y el motivo de consulta.",
             "metadata": {"tipo": "clase", "fuente": "mpna-teorico.md", "seccion": "Anamnesis", "pagina": 3}}


@pytest.fixture
def fake_model(monkeypatch):
    seen = []

    class Model:
        def invoke(self, messages):
            seen.append(messages)
            return SimpleNamespace(respuesta="  Dale, arrancá por la ficha patronímica.  ")

    monkeypatch.setattr(tutor, "_model", lambda: Model())
    monkeypatch.setattr(tutor, "_search", lambda materia, pregunta: [FRAGMENTO, FRAGMENTO])
    return seen


def test_answer_uses_the_course_material(fake_model):
    out = tutor.answer("mpna", "¿Cómo era la anamnesis?", "principiante", [])
    assert out["texto"] == "Dale, arrancá por la ficha patronímica."
    assert out["fuentes"] == [{"tipo": "clase", "fuente": "mpna-teorico.md", "seccion": "Anamnesis", "pagina": 3}]
    system = fake_model[0][0].content
    assert FRAGMENTO["texto"] in system


def test_each_level_gets_its_own_instruction():
    normal = prompts.tutor_prompt("normal", [], [])
    principiante = prompts.tutor_prompt("principiante", [], [])
    assert "NO le des la respuesta completa" in normal and "respuesta directa" not in normal
    assert "respuesta directa" in principiante
    assert "no se encontró material" in normal  # without fragments it must say so, not invent


def test_the_tutor_never_receives_the_case(fake_model):
    """It only sees what the student has seen: no diagnosis, no hidden facts, no grilla."""
    case = load_case(CASE)
    sid = graph.new_session(CASE, USER, nivel="principiante")
    graph.tutor(sid, "¿Qué le pregunto ahora?", USER)
    system = fake_model[0][0].content
    assert case["diagnostico"]["principal"] not in system
    hidden = [h["respuesta"] for h in case["anamnesis"]]
    assert not any(r in system for r in hidden)


def test_tutor_questions_stay_out_of_the_consultation(fake_model):
    sid = graph.new_session(CASE, USER)
    graph.tutor(sid, "¿Cómo era la anamnesis?", USER)
    s = graph._state(sid, USER)
    assert s.get("transcript", []) == []  # the patient never sees it, and it isn't a turn
    assert s["tutor"] == [{"pregunta": "¿Cómo era la anamnesis?", "respuesta": "Dale, arrancá por la ficha patronímica."}]


def test_tutor_limits(fake_model, monkeypatch):
    sid = graph.new_session(CASE, USER)
    with pytest.raises(PermissionError):
        graph.tutor(sid, "hola", {"email": "otro@example.com"})
    monkeypatch.setattr(graph, "MAX_TUTOR", 1)
    graph.tutor(sid, "una", USER)
    with pytest.raises(ValueError):
        graph.tutor(sid, "dos", USER)


def test_normal_feedback_counts_the_tutor_and_beginner_doesnt(fake_model, monkeypatch):
    from agents import feedback

    monkeypatch.setattr(feedback, "evaluate", lambda case, s: {"score": 50, "items": []})
    for nivel, esperado in (("normal", 2), ("principiante", None)):
        sid = graph.new_session(CASE, USER, nivel=nivel)
        graph.tutor(sid, "una", USER)
        graph.tutor(sid, "otra", USER)
        fb = graph.finish(sid, USER)["feedback"]
        assert fb.get("tutor_consultas") == esperado
        with pytest.raises(ValueError):  # finished: no more questions
            graph.tutor(sid, "y ahora?", USER)
