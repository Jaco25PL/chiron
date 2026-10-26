"""The router generates the patient's reply in parallel (speculative): fake models, no Gemini."""

import threading
from types import SimpleNamespace

import pytest

from agents import graph
from llm import gemini

USER = {"email": "spec@example.com", "name": None}


class Fake:
    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def invoke(self, _messages):
        self.calls += 1
        return self.fn()


@pytest.fixture
def fakes(monkeypatch):
    m = {
        "router": Fake(lambda: SimpleNamespace(intent="anamnesis")),
        "patient": Fake(lambda: SimpleNamespace(respuesta="Me falta el aire.", hechos_usados=[])),
        "exam": Fake(lambda: SimpleNamespace(ids=[], no_disponible=[])),
        "labs": Fake(lambda: SimpleNamespace(indices=[], no_disponible=[])),
    }
    monkeypatch.setattr(graph, "models", lambda: m)
    return m


def test_anamnesis_uses_the_speculative_reply(fakes):
    sid = graph.new_session("mpna-disnea-icc", USER)
    out = graph.send(sid, "¿Qué lo trae?", USER)
    assert [r["role"] for r in out["replies"]] == ["paciente"]
    assert fakes["patient"].calls == 1  # not generated twice
    assert {"router", "anamnesis"} <= set(out["debug"]["timings"])


def test_router_and_patient_run_at_the_same_time(fakes):
    router_on, patient_on = threading.Event(), threading.Event()

    def route():  # waits for the patient: sequential calls would time out here
        router_on.set()
        assert patient_on.wait(5)
        return SimpleNamespace(intent="anamnesis")

    def reply():
        patient_on.set()
        assert router_on.wait(5)
        return SimpleNamespace(respuesta="Hace una semana.", hechos_usados=[])

    fakes["router"].fn, fakes["patient"].fn = route, reply
    sid = graph.new_session("mpna-disnea-icc", USER)
    assert graph.send(sid, "¿Desde cuándo?", USER)["replies"][0]["text"] == "Hace una semana."


def test_other_intents_discard_the_speculative_reply(fakes):
    fakes["router"].fn = lambda: SimpleNamespace(intent="examen")
    sid = graph.new_session("mpna-disnea-icc", USER)
    out = graph.send(sid, "Le tomo la presión", USER)
    assert [r["role"] for r in out["replies"]] == ["docente"]
    assert fakes["exam"].calls == 1


def test_failed_speculation_falls_back_to_the_anamnesis_node(fakes):
    def flaky():
        if fakes["patient"].calls == 1:
            raise RuntimeError("boom")
        return SimpleNamespace(respuesta="Sí, de noche.", hechos_usados=[])

    fakes["patient"].fn = flaky
    sid = graph.new_session("mpna-disnea-icc", USER)
    out = graph.send(sid, "¿Le pasa de noche?", USER)
    assert out["replies"] == [{"role": "paciente", "text": "Sí, de noche."}]
    assert fakes["patient"].calls == 2


def test_speculative_thread_keeps_the_paid_key_user(fakes):
    seen = []

    def reply():
        seen.append(gemini._usuario.get())
        return SimpleNamespace(respuesta="No.", hechos_usados=[])

    fakes["patient"].fn = reply
    sid = graph.new_session("mpna-disnea-icc", USER)
    with gemini.usuario(USER["email"]):
        graph.send(sid, "¿Fuma?", USER)
    assert seen == [USER["email"]]
