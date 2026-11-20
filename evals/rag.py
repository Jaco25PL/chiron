"""Retrieval eval for the RAG the study companion uses: does the search bring the chunks that hold the answer?

    python evals/rag.py            # runs the gold set against the real search, prints the metrics
    python evals/rag.py --detalle  # ... plus what came back for every question that missed
    python evals/run.py rag        # the same, logged to LangSmith as an experiment (chiron-rag)

The gold set (evals/rag_gold.json) says, for each question, where its answer is in the course material, by
content (source + a phrase of the chunk), so it survives re-chunking. No LLM judges anything: the metrics
compare lists. The only model call is the query embedding, cached in evals/.cache/ so re-running (or
comparing search variants) is free and deterministic. Needs DATABASE_URL (the pgvector index).

Metrics, per question (averaged per category):
- hit@1 / hit@5   a relevant chunk is first / among the K the companion gets
- recall@5        share of the gold locations found in the K (a question can have its answer in 2-3 places)
- rr              1 / rank of the first relevant chunk (MRR when averaged)
- top1            cosine distance of the best chunk: on `fuera` questions (not in the material) it should be
                  high; the gap with the in-material ones is what a relevance threshold would use
"""

import json
import re
import sys
import threading
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD = ROOT / "evals" / "rag_gold.json"
CACHE = ROOT / "evals" / ".cache" / "rag_embeddings.json"
MATERIA = "mpna"
K = 5  # what agents/tutor.py FRAGMENTS gives the companion
CATEGORIAS = ["concepto", "termino", "dato", "coloquial", "contextual", "fuera"]


# --- matching (pure, unit-tested) ---------------------------------------------------


def norm(text: str) -> str:
    """Lowercase, no accents, no markdown emphasis, single spaces: how gold phrases are compared."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.replace("*", "").replace("`", "")).strip()


def es_relevante(chunk: dict, gold: dict) -> bool:
    """`chunk` ({texto, metadata}) is the gold location `gold` ({fuente, contiene})."""
    return (norm(chunk["metadata"].get("fuente", "")).endswith(norm(gold["fuente"]))
            and norm(gold["contiene"]) in norm(chunk["texto"]))


def metricas(chunks: list[dict], relevantes: list[dict], k: int = K) -> dict:
    """The per-question metrics for the ranked `chunks` against the gold `relevantes`."""
    top = chunks[:k]
    top1 = chunks[0]["score"] if chunks else None
    if not relevantes:
        return {"top1": top1}
    rank = next((i + 1 for i, c in enumerate(top) if any(es_relevante(c, g) for g in relevantes)), None)
    found = sum(any(es_relevante(c, g) for c in top) for g in relevantes)
    return {"hit@1": int(rank == 1), f"hit@{k}": int(rank is not None), f"recall@{k}": found / len(relevantes),
            "rr": 1 / rank if rank else 0.0, "top1": top1}


def load_gold() -> list[dict]:
    return json.loads(GOLD.read_text(encoding="utf-8"))["preguntas"]


# --- running the real search ----------------------------------------------------------


_cache: dict | None = None
_lock = threading.Lock()  # LangSmith's evaluate calls the target from several threads


def _embedding(pregunta: str) -> list[float]:
    """The query's embedding, from evals/.cache/ or computed once and saved (atomically)."""
    global _cache
    from llm.gemini import MODELS
    from rag.search import DIMS, embed_query

    key = f"{MODELS['embedding'][0]}:{DIMS}:{pregunta}"
    with _lock:
        if _cache is None:
            _cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        if key in _cache:
            return _cache[key]
    vec = embed_query(pregunta)
    with _lock:
        _cache[key] = vec
        CACHE.parent.mkdir(exist_ok=True)
        tmp = CACHE.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(_cache), encoding="utf-8")
        tmp.replace(CACHE)
    return vec


def buscar(preguntas: list[str]) -> dict[str, list[dict]]:
    """The real search (rag/search.py, as the companion calls it) for each question, embeddings cached."""
    from rag.search import search_vector

    return {p: search_vector(MATERIA, _embedding(p), k=K) for p in preguntas}


def resumen(filas: list[tuple[dict, dict]]) -> str:
    """Table of averages per category (rows: (gold question, its metrics))."""
    keys = ["hit@1", f"hit@{K}", f"recall@{K}", "rr", "top1"]
    lines = [f"{'categoria':11} {'n':>3} " + " ".join(f"{k:>9}" for k in keys)]
    for cat in [*CATEGORIAS, "total"]:
        rows = [m for q, m in filas if cat in (q["categoria"], "total") and (cat != "total" or q["categoria"] != "fuera")]
        if not rows:
            continue
        cells = []
        for k in keys:
            vals = [m[k] for m in rows if m.get(k) is not None]
            cells.append(f"{sum(vals) / len(vals):9.2f}" if vals else f"{'':9}")
        lines.append(f"{cat if cat != 'total' else 'total*':11} {len(rows):3} " + " ".join(cells))
    lines.append("* total without `fuera`. top1 = cosine distance of the best chunk (lower = closer).")
    return "\n".join(lines)


def main():
    from llm import gemini  # noqa: F401  (loads .env)

    gold = load_gold()
    resultados = buscar([q["pregunta"] for q in gold])
    filas = [(q, metricas(resultados[q["pregunta"]], q["relevantes"])) for q in gold]
    print(resumen(filas))
    dentro = [m["top1"] for q, m in filas if q["categoria"] != "fuera"]
    fuera = [m["top1"] for q, m in filas if q["categoria"] == "fuera"]
    print(f"\ntop1 in the material: {min(dentro):.3f}-{max(dentro):.3f} | outside: {min(fuera):.3f}-{max(fuera):.3f}")
    fallas = [(q, m) for q, m in filas if q["relevantes"] and not m[f"hit@{K}"]]
    print(f"\nMissed ({len(fallas)}): " + ", ".join(q["id"] for q, _ in fallas))
    if "--detalle" in sys.argv:
        for q, _ in fallas:
            print(f"\n## {q['id']} [{q['categoria']}] {q['pregunta']}")
            for c in resultados[q["pregunta"]]:
                m = c["metadata"]
                print(f"  {c['score']:.3f} {m.get('fuente', '')[:40]:40} p{m.get('pagina')} | {c['texto'][:90]!r}")


if __name__ == "__main__":
    main()
