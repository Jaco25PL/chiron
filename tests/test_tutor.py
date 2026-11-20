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
    monkeypatch.setattr(tutor, "_rewriter", lambda: Rewriter(lambda prompt: "pregunta reescrita"))
    return seen


class Rewriter:
    def __init__(self, fn):
        self.fn, self.prompts = fn, []

    def invoke(self, messages):
        self.prompts.append(messages[0].content)
        return SimpleNamespace(consulta=self.fn(messages[0].content))


TURNS = [{"role": "paciente", "text": "A veces me despierto ahogado y me tengo que sentar."}]


def test_search_query_resolves_the_question_with_the_last_turns(monkeypatch):
    rw = Rewriter(lambda prompt: " ¿Qué es la disnea paroxística nocturna? ")
    monkeypatch.setattr(tutor, "_rewriter", lambda: rw)
    assert tutor.search_query("¿Cómo se llama eso?", TURNS) == "¿Qué es la disnea paroxística nocturna?"
    assert "me despierto ahogado" in rw.prompts[0] and "¿Cómo se llama eso?" in rw.prompts[0]


def test_search_query_without_turns_or_on_failure_keeps_the_question(monkeypatch):
    def boom(prompt):
        raise RuntimeError("quota")

    monkeypatch.setattr(tutor, "_rewriter", lambda: Rewriter(boom))
    assert tutor.search_query("¿Qué es el CAGE?", []) == "¿Qué es el CAGE?"
    assert tutor.search_query("¿Cómo se llama eso?", TURNS) == "¿Cómo se llama eso?"


def test_a_slow_rewrite_falls_back_to_the_question(monkeypatch):
    import time

    monkeypatch.setattr(tutor, "REWRITE_DEADLINE", 0.05)
    monkeypatch.setattr(tutor, "_rewriter", lambda: Rewriter(lambda prompt: time.sleep(0.5) or "tarde"))
    assert tutor.search_query("¿Cómo se llama eso?", TURNS) == "¿Cómo se llama eso?"


def test_the_rewrite_thread_knows_the_user(monkeypatch):
    """The paid key is chosen by the user in a ContextVar; a bare thread wouldn't see it (FINDINGS #22)."""
    from llm import gemini

    seen = []
    monkeypatch.setattr(tutor, "_rewriter", lambda: Rewriter(lambda prompt: seen.append(gemini._usuario.get()) or "x"))
    with gemini.usuario("alumna@example.com"):
        tutor.search_query("¿Cómo se llama eso?", TURNS)
    assert seen == ["alumna@example.com"]


def test_the_search_gets_the_rewritten_question(fake_model, monkeypatch):
    searched = []
    monkeypatch.setattr(tutor, "_search", lambda materia, pregunta: searched.append(pregunta) or [FRAGMENTO])
    tutor.answer("mpna", "¿Cómo se llama eso?", "normal", TURNS)
    assert searched == ["pregunta reescrita"]


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
