"""BM25 and rank fusion for the hybrid search mode (rag/lexical.py, rag/search.py)."""

from rag.lexical import BM25, tokens
from rag.search import rrf


def test_tokens_drop_accents_stopwords_and_stem():
    assert tokens("¿Para qué sirve el monofilamento en el pie diabético?") == ["monofi", "pie", "diabet"]
    assert tokens("Lasègue") == tokens("Lasegue")


def test_bm25_ranks_the_rare_exact_term_first():
    docs = [{"id": "a", "texto": "Punto de Guyón y punto de Surraco (costomuscular)"},
            {"id": "b", "texto": "El punto de partida del examen es la inspección"},
            {"id": "c", "texto": "Auscultación cardíaca"}]
    assert BM25(docs).top("¿Qué es el punto de Surraco?", 3) == ["a", "b"]  # c shares no token


def test_bm25_filters_by_type():
    docs = [{"id": "a", "texto": "salbutamol", "tipo": "grilla"}, {"id": "b", "texto": "salbutamol", "tipo": "apunte"}]
    assert BM25(docs).top("salbutamol", 5, tipo="apunte") == ["b"]


def test_rrf_rewards_agreement_and_respects_weights():
    assert rrf([["a", "b"], ["b", "c"]])[0] == "b"  # in both lists beats 1st in only one
    assert rrf([["a", "b"], ["b", "a"]], [1.0, 0.1]) == ["a", "b"]
