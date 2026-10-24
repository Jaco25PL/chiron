import os

os.environ["CHIRON_FAKE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture
def case_id():
    cases = client.get("/api/cases", params={"materia": "mpna"}).json()
    return cases[0]["id"]


def test_list_cases_no_revela_diagnostico():
    r = client.get("/api/cases", params={"materia": "mpna"})
    assert r.status_code == 200
    cases = r.json()
    assert cases
    for c in cases:
        assert {"id", "materia", "titulo", "dificultad", "grillas", "paciente"} <= c.keys()
        assert {"nombre", "edad", "sexo"} <= c["paciente"].keys()
        assert "diagnostico" not in c


def test_create_session(case_id):
    r = client.post("/api/sessions", json={"case_id": case_id})
    assert r.status_code == 200
    assert r.json()["session_id"]


def test_create_session_caso_inexistente():
    r = client.post("/api/sessions", json={"case_id": "no-existe"})
    assert r.status_code == 404
    assert "error" in r.json()


def test_send_message_y_get_session(case_id):
    sid = client.post("/api/sessions", json={"case_id": case_id}).json()["session_id"]

    r = client.post(f"/api/sessions/{sid}/messages", json={"text": "¿Qué lo trae por acá?"})
    assert r.status_code == 200
    body = r.json()
    assert body["replies"] and body["replies"][0]["role"] in ("paciente", "docente")
    assert {"intent", "facts", "exams", "studies", "model", "latency_ms"} <= body["debug"].keys()

    r = client.post(f"/api/sessions/{sid}/messages", json={"text": "Le tomo la presión"})
    assert r.json()["replies"][0]["role"] == "docente"

    s = client.get(f"/api/sessions/{sid}").json()
    assert s["case_id"] == case_id
    assert [m["role"] for m in s["transcript"]][:2] == ["estudiante", "paciente"]
    assert s["total_facts"] > 0
    assert len(s["revealed_facts"]) >= 1
    assert s["exams_done"]
    assert {"studies_requested", "diagnosis_proposed", "finished"} <= s.keys()


def test_send_message_vacio_y_sesion_inexistente(case_id):
    sid = client.post("/api/sessions", json={"case_id": case_id}).json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": "  "}).status_code == 400
    r = client.post("/api/sessions/nope/messages", json={"text": "hola"})
    assert r.status_code == 404 and "error" in r.json()


def test_rag_search_monkeypatched(monkeypatch):
    import rag.query

    def fake_search(materia, pregunta, k=5, tipo=None):
        return [{"texto": f"{materia}:{pregunta}", "metadata": {"fuente": "x.md", "tipo": tipo}, "score": 0.1}] * k

    monkeypatch.setattr(rag.query, "search", fake_search)
    r = client.get("/api/rag/search", params={"q": "disnea", "k": 2, "tipo": "grilla"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2 and data[0]["metadata"]["tipo"] == "grilla"


def test_frontend_servido():
    r = client.get("/")
    assert r.status_code == 200
    assert "Chiron" in r.text
