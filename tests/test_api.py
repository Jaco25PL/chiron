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
        # like the real exam: the student only knows the patient's name and sex
        assert c.keys() == {"id", "materia", "paciente"}
        assert c["paciente"].keys() == {"nombre", "sexo"}
        # the id is opaque: internal ids (e.g. "mpna-itu-pna-diabetica") spell out the diagnosis
        assert "-" not in c["id"] and not c["id"].startswith("mpna")


def test_random_case_picks_one_on_the_server(case_id):
    r = client.post("/api/sessions", json={"case_id": "aleatorio"})
    assert r.status_code == 200
    body = r.json()
    public_ids = {c["id"] for c in client.get("/api/cases").json()}
    assert body["case"]["id"] in public_ids
    assert body["case"]["paciente"].keys() == {"nombre", "sexo"}


def test_session_payload_never_exposes_internal_case_data(case_id):
    sid = client.post("/api/sessions", json={"case_id": case_id}).json()["session_id"]
    raw = client.get(f"/api/sessions/{sid}").text
    for leak in ("mpna-", "titulo", "dificultad", "diagnostico", "grillas"):
        assert leak not in raw


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
    assert s["case"]["id"] == case_id
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


# --- voice (face-to-face mode) ---------------------------------------------------------

def test_voice_speaks_the_last_patient_reply(case_id):
    sid = client.post("/api/sessions", json={"case_id": case_id}).json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/voz").status_code == 404  # nothing said yet
    client.post(f"/api/sessions/{sid}/messages", json={"text": "Hola, buenas tardes"})
    r = client.post(f"/api/sessions/{sid}/voz")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF" and r.content[8:12] == b"WAVE"


def test_voice_style_and_choice_stay_on_the_server():
    from cases.catalog import load_case
    from llm.tts import VOICES, style

    case = load_case("mpna-itu-pna-diabetica")
    assert "61 años" in style(case) and "mujer" in style(case)  # age is used for the voice only
    assert VOICES[case["paciente"]["sexo"]] == "Sulafat"


def test_tts_audio_keeps_only_the_sound():
    import struct

    from llm.tts import to_pcm, to_wav

    pcm = b"\x01\x02" * 100
    assert to_pcm(pcm) == pcm  # models that return raw PCM
    firma = b"C2PA" + struct.pack("<I", 8) + b"x" * 8  # provenance chunk after the audio
    wav = to_wav(pcm)
    wav = wav[:4] + struct.pack("<I", len(wav) - 8 + len(firma)) + wav[8:] + firma
    assert to_pcm(wav) == pcm  # the signature must not be played as sound
