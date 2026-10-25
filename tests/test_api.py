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

def test_call_streams_the_reply_and_then_the_voice(case_id):
    import base64
    import json

    sid = client.post("/api/sessions", json={"case_id": case_id}).json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/messages", params={"voz": 1}, json={"text": "Hola, buenas tardes"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/x-ndjson"
    lines = [json.loads(line) for line in r.text.splitlines()]
    assert [x["tipo"] for x in lines] == ["respuesta", "audio", "audio", "fin"]  # text first, then the voice
    assert lines[0]["replies"][0]["role"] == "paciente"
    assert len(base64.b64decode(lines[1]["pcm"])) % 2 == 0  # whole 16-bit samples

    # the docente's reports are read, not spoken
    r = client.post(f"/api/sessions/{sid}/messages", params={"voz": 1}, json={"text": "Le tomo la presión arterial"})
    assert [json.loads(x)["tipo"] for x in r.text.splitlines()] == ["respuesta", "fin"]


def test_chat_replies_stay_plain_json(case_id):
    sid = client.post("/api/sessions", json={"case_id": case_id}).json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/messages", json={"text": "Hola"})
    assert r.headers["content-type"] == "application/json" and r.json()["replies"]


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


def test_review_hides_the_judge_and_keeps_labels():
    r = client.get("/api/revision")
    assert r.status_code == 200
    body = r.json()
    assert body["criterios"][0] == "no_revela_diagnostico" and body["items"]
    assert "juez" not in r.text  # the judge's verdict would anchor the reviewer
    item = body["items"][0]
    r = client.post(f"/api/revision/{item['id']}", json={"etiquetas": {"en_personaje": False}, "nota": "jerga"})
    assert r.status_code == 200
    again = next(i for i in client.get("/api/revision").json()["items"] if i["id"] == item["id"])
    assert again["etiquetas"] == {"en_personaje": False} and again["nota"] == "jerga"
    assert client.post("/api/revision/nope", json={"etiquetas": {}}).status_code == 404
    assert client.post(f"/api/revision/{item['id']}", json={"etiquetas": {"otro": True}}).status_code == 400


def test_review_is_only_for_listed_reviewers(monkeypatch):
    from api.security import sign

    monkeypatch.setenv("CHIRON_BACKEND_SECRET", "s")
    monkeypatch.setenv("CHIRON_REVIEWERS", "Sofia@example.com")

    def headers(email):
        import time

        ts = str(int(time.time()))
        return {"x-chiron-user": email, "x-chiron-name": "", "x-chiron-ts": ts, "x-chiron-sig": sign("s", email, "", ts)}

    assert client.get("/api/revision", headers=headers("alumno@example.com")).status_code == 403
    assert client.get("/api/revision", headers=headers("sofia@example.com")).status_code == 200


def test_review_kappa():
    from evals.review import kappa

    assert kappa([(True, True), (False, False)]) == 1
    assert kappa([(True, True), (True, True)]) is None  # everyone passes: kappa says nothing


# --- levels: "principiante" shows the checklist, "normal" doesn't -------------------------------

def test_normal_level_never_sends_the_checklist(case_id):
    r = client.post("/api/sessions", json={"case_id": case_id})
    assert "checklist" not in r.json()
    sid = r.json()["session_id"]
    assert "checklist" not in client.post(f"/api/sessions/{sid}/messages", json={"text": "¿Qué lo trae por acá?"}).json()
    s = client.get(f"/api/sessions/{sid}").json()
    assert "checklist" not in s and s["nivel"] == "normal"


def test_beginner_checklist_ticks_as_the_student_asks():
    from cases.catalog import load_case, public_id

    case = load_case("mpna-disnea-icc")
    r = client.post("/api/sessions", json={"case_id": public_id(case["id"]), "nivel": "principiante"})
    assert r.status_code == 200
    lista = r.json()["checklist"]
    assert lista and not any(x["hecho"] for x in lista)
    assert {x["tipo"] for x in lista} <= {"hecho", "examen", "estudio"}
    assert all(x.keys() == {"id", "texto", "tipo", "hecho"} for x in lista)

    # the fake backend matches the question against the case facts: "inicio" covers its grilla item
    sid = r.json()["session_id"]
    inicio = next(h for h in case["anamnesis"] if h["id"] == "inicio")
    body = client.post(f"/api/sessions/{sid}/messages", json={"text": inicio["preguntas_ejemplo"][0]}).json()
    assert body["debug"]["facts"] == ["inicio"]
    hechos = {x["texto"] for x in body["checklist"] if x["hecho"]}
    assert {k.split("::", 1)[1] for k in inicio["grilla_items"]} <= hechos

    s = client.get(f"/api/sessions/{sid}").json()
    assert s["nivel"] == "principiante" and s["checklist"] == body["checklist"]


def test_beginner_checklist_rides_along_with_the_voice():
    import json

    sid = client.post("/api/sessions", json={"case_id": "aleatorio", "nivel": "principiante"}).json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/messages", params={"voz": 1}, json={"text": "Hola, buenas tardes"})
    primera = json.loads(r.text.splitlines()[0])
    assert primera["tipo"] == "respuesta" and primera["checklist"]


def test_beginner_checklist_never_names_the_diagnosis():
    from cases import catalog

    for c in catalog.list_public("mpna"):
        r = client.post("/api/sessions", json={"case_id": c["id"], "nivel": "principiante"})
        assert r.json()["checklist"]
        case = catalog.load_case(catalog.resolve(c["id"]))
        raw = r.text.lower()
        assert case["diagnostico"]["principal"].lower() not in raw
        for key in case["diagnostico"].get("grilla_items", []):
            assert key.split("::", 1)[1].lower() not in raw


def test_invalid_level_is_rejected(case_id):
    r = client.post("/api/sessions", json={"case_id": case_id, "nivel": "experto"})
    assert r.status_code == 422 and "error" in r.json()
