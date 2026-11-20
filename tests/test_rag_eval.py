"""The retrieval eval's matching and metrics, and that its gold set still points at real chunks."""

import json
from pathlib import Path

import pytest

from evals.rag import CATEGORIAS, es_relevante, load_gold, metricas, norm

CHUNKS = Path(__file__).resolve().parent.parent / "data" / "ecoe" / "mpna" / "chunks.jsonl"


def chunk(texto, fuente="mpna-teorico.md", score=0.3):
    return {"texto": texto, "metadata": {"fuente": fuente}, "score": score}


def test_norm_ignores_accents_case_markdown_and_spacing():
    assert norm("**Ortopnea**  Es la  disnea\nque") == "ortopnea es la disnea que"
    assert norm("Lasègue ≥126") == "lasegue ≥126"


def test_relevant_needs_source_and_phrase():
    gold = {"fuente": "Sim-4_GRILLA-MANEJO CLÍNICO-Crisis-Asmatica.pdf", "contiene": "4 a 8 puff"}
    assert es_relevante(chunk("- 4 a 8 puff cada 20min", "new/Sim-4_GRILLA-MANEJO CLÍNICO-Crisis-Asmática.pdf"), gold)
    assert not es_relevante(chunk("- 4 a 8 puff cada 20min", "asma.md"), gold)
    assert not es_relevante(chunk("otra cosa", "new/Sim-4_GRILLA-MANEJO CLÍNICO-Crisis-Asmática.pdf"), gold)


def test_metrics_rank_and_recall():
    gold = [{"fuente": "mpna-teorico.md", "contiene": "giordano"}, {"fuente": "grillas-mpna.pdf", "contiene": "giordano"}]
    ranked = [chunk("nada", score=0.2), chunk("signo de Giordano", score=0.25), chunk("x"), chunk("y"), chunk("z"),
              chunk("Maniobra de Giordano", "grillas-mpna.pdf")]  # 6th: outside the top 5
    m = metricas(ranked, gold)
    assert (m["hit@1"], m["hit@5"], m["recall@5"], m["rr"], m["top1"]) == (0, 1, 0.5, 0.5, 0.2)
    assert metricas([chunk("nada")] * 5, gold)["hit@5"] == 0


def test_out_of_scope_questions_only_report_the_best_distance():
    assert metricas([chunk("x", score=0.43)], []) == {"top1": 0.43}


@pytest.fixture(scope="module")
def chunks():
    return [json.loads(line) for line in CHUNKS.read_text(encoding="utf-8").splitlines()]


def test_gold_set_is_well_formed():
    gold = load_gold()
    assert len({q["id"] for q in gold}) == len(gold), "duplicate ids"
    assert {q["categoria"] for q in gold} <= set(CATEGORIAS)
    for q in gold:
        assert bool(q["relevantes"]) == (q["categoria"] != "fuera"), q["id"]


def test_every_gold_location_exists_in_the_chunks(chunks):
    """If re-chunking or re-cleaning drops a phrase, the label must be fixed, not silently count as a miss."""
    missing = [f"{q['id']}: {g['fuente']} / {g['contiene']!r}"
               for q in load_gold() for g in q["relevantes"] if not any(es_relevante(c, g) for c in chunks)]
    assert not missing, "gold phrases not found in chunks.jsonl:\n" + "\n".join(missing)
