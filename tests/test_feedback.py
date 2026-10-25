import json
from types import SimpleNamespace

import pytest

from agents import feedback, grilla
from cases.catalog import case_ids, load_case

ITU = "mpna-itu-pna-diabetica"


def _llm(monkeypatch, out=None, error=None):
    """Replaces the docente's LLM with a canned answer (or an error); returns the call log."""
    calls = []

    class Judge:
        def invoke(self, messages):
            calls.append(messages)
            if error:
                raise error
            return out

    monkeypatch.setattr(feedback, "_judge", lambda: Judge())
    return calls


def _answer(ratings: dict, bien=(), falto=(), consejos=()):
    return SimpleNamespace(items=[SimpleNamespace(id=i, calificacion=c) for i, c in ratings.items()],
                           bien=list(bien), falto=list(falto), consejos=list(consejos))


def test_score_uses_the_grilla_scale_and_skips_global():
    r = lambda tipo, c: {"tipo": tipo, "calificacion": c}  # noqa: E731
    assert feedback.score([r("hecho", "Excelente"), r("examen", "No realizado")]) == 50
    assert feedback.score([r("hecho", "Bien"), r("conducta", "Regular"), r("plan", "Excelente")]) == 67
    assert feedback.score([r("hecho", "Excelente"), r("global", "No realizado")]) == 100
    assert feedback.score([r("conducta", None), r("hecho", "Excelente")]) == 100  # unrated: out of the score
    assert feedback.score([]) == 0


def test_no_credit_without_evidence_and_at_least_regular_with_it():
    for kind in feedback.EVIDENCE_KINDS:
        assert feedback.guard(kind, False, "Excelente") == "No realizado"
        assert feedback.guard(kind, True, "No realizado") == "Regular"
        assert feedback.guard(kind, True, None) == "Regular"
        assert feedback.guard(kind, True, "Bien") == "Bien"
    # the app can't see conduct, plan or diagnosis: the docente's rating stands
    assert feedback.guard("conducta", False, "Excelente") == "Excelente"
    assert feedback.guard("diagnostico", False, "Bien") == "Bien"


def test_the_diagnosis_filter_drops_only_the_sentences_that_name_it():
    terms = feedback.forbidden_terms(load_case(ITU))
    out = feedback.scrub([
        "Muy bien el saludo. Planteaste bien la pielonefritis.",
        "Pensá en una infección urinaria complicada.",
        "La próxima, preguntá por los factores de riesgo cardiovascular antes de pasar al examen.",
        "Era una ITU alta; buen examen de la fosa lumbar.",
        "Preguntá cómo viene controlada la diabetes.",  # the patient says it herself: not the secret
    ], terms)
    assert out == [
        "Muy bien el saludo.",
        "La próxima, preguntá por los factores de riesgo cardiovascular antes de pasar al examen.",
        "buen examen de la fosa lumbar.",
        "Preguntá cómo viene controlada la diabetes.",
    ]
    for cid in case_ids():
        case = load_case(cid)
        assert feedback.reveals(case["diagnostico"]["principal"], feedback.forbidden_terms(case))


def test_feedback_never_shows_diagnosis_or_plan_items(monkeypatch):
    for cid in case_ids():
        case = load_case(cid)
        _llm(monkeypatch, _answer({it["id"]: "Bien" for it in grilla.items(case)},
                                  bien=[f"Planteaste {case['diagnostico']['principal']}."]))
        fb = feedback.evaluate(case, {})
        text = json.dumps(fb, ensure_ascii=False)
        assert case["diagnostico"]["principal"] not in text and not fb["bien"]
        for key in case["diagnostico"].get("grilla_items", []):
            assert key.split("::", 1)[1] not in text
        for r in fb["items"]:
            if r["tipo"] in feedback.HIDDEN_LABELS:
                assert r["texto"] == feedback.HIDDEN_LABELS[r["tipo"]]
            assert not feedback.reveals(r["texto"], feedback.forbidden_terms(case))


def test_evaluate_applies_the_guardrails_to_the_docente(monkeypatch):
    case = load_case("mpna-dolor-toracico-angina")
    its = grilla.items(case)
    asked = next(i for i in its if "aparicion" in i["facts"])
    missed = next(i for i in its if i["kind"] == "hecho" and i["id"] != asked["id"] and "aparicion" not in i["facts"])
    glob = next(i for i in its if i["kind"] == "global")
    calls = _llm(monkeypatch, _answer({asked["id"]: "No realizado", missed["id"]: "Excelente", glob["id"]: "Excelente"},
                                      bien=["Saludaste y te presentaste."], consejos=["a", "b", "c", "d"]))
    fb = feedback.evaluate(case, {"revealed_facts": ["aparicion"], "transcript": [{"role": "estudiante", "text": "hola"}]})
    by_id = {r["id"]: r for r in fb["items"]}
    assert by_id[asked["id"]]["calificacion"] == "Regular" and by_id[asked["id"]]["evidencia"]
    assert by_id[missed["id"]]["calificacion"] == "No realizado"
    assert by_id[glob["id"]]["calificacion"] == "Excelente"
    assert fb["parcial"] is False and fb["bien"] == ["Saludaste y te presentaste."] and len(fb["consejos"]) == 3
    assert fb["score"] == feedback.score(fb["items"])
    prompt = calls[0][0].content
    assert "estudiante: hola" in prompt and case["diagnostico"]["principal"] in prompt  # the docente needs it
    assert f"{asked['id']} | hecho | evidencia: sí" in prompt


def test_a_study_that_is_not_indicated_is_earned_by_not_ordering_it(monkeypatch):
    case = load_case(ITU)
    item = next(i for i in grilla.items(case) if i["texto"] == "No es necesaria PC imagenológica")
    _llm(monkeypatch, _answer({item["id"]: "Excelente"}))
    rating = lambda st: next(r for r in feedback.evaluate(case, st)["items"] if r["id"] == item["id"])  # noqa: E731
    assert rating({})["calificacion"] == "Excelente" and rating({})["evidencia"]
    ordered = rating({"studies_requested": ["Ecografía del aparato urinario"]})
    assert ordered["calificacion"] == "No realizado" and not ordered["evidencia"]


def test_without_the_llm_the_feedback_comes_from_coverage(monkeypatch):
    case = load_case("mpna-dolor-toracico-angina")
    _llm(monkeypatch, error=RuntimeError("429 RESOURCE_EXHAUSTED"))
    fb = feedback.evaluate(case, {"revealed_facts": ["aparicion"]})
    assert fb["parcial"] is True and fb["consejos"] == []
    rated = [r for r in fb["items"] if r["calificacion"]]
    assert rated and {r["tipo"] for r in rated} <= set(feedback.EVIDENCE_KINDS)
    # covered -> "Bien" (quality unknown), the rest "No realizado"
    assert {r["calificacion"] for r in rated if r["evidencia"]} == {"Bien"}
    assert {r["calificacion"] for r in rated if not r["evidencia"]} == {"No realizado"}
    assert fb["score"] == round(100 * 2 * sum(r["evidencia"] for r in rated) / (3 * len(rated))) > 0
    assert 0 < len(fb["falto"]) <= feedback.MAX_FALTO
    assert feedback.para_la_proxima(fb) == fb["falto"][:2]


def test_finish_computes_the_feedback_once_and_keeps_it_in_the_history(monkeypatch):
    from agents import graph

    calls = _llm(monkeypatch, _answer({}, consejos=["La próxima, presentate antes de preguntar."]))
    user = {"email": "ana@example.com", "name": "Ana"}
    sid = graph.new_session(ITU, user, mode="cara")
    first = graph.finish(sid, user)
    again = graph.finish(sid, user)
    assert len(calls) == 1 and first["finished"] and first["feedback"] == again["feedback"]
    assert first["feedback"]["consejos"] == ["La próxima, presentate antes de preguntar."]

    hist = graph.historial(user)
    assert hist[0]["id"] == sid and hist[0]["modo"] == "cara" and hist[0]["score"] == first["feedback"]["score"]
    assert hist[0]["paciente"].keys() == {"nombre", "sexo"}
    assert hist[0]["para_la_proxima"] == ["La próxima, presentate antes de preguntar."]
    assert all(h["id"] != sid for h in graph.historial({"email": "otro@example.com"}))
    with pytest.raises(PermissionError):
        graph.finish(sid, {"email": "otro@example.com"})
