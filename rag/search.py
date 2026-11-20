"""RAG retrieval over Postgres + pgvector (the server's search path; no Chroma needed).

    from rag.search import search
    search("mpna", "¿cuándo pedir urocultivo?", k=5, tipo="clase")

Vector search by default. MODO="hibrida" adds BM25 (exact words, rag/lexical.py): each ranks CANDIDATES
chunks and the lists are fused with reciprocal rank fusion (RRF). Measured with evals/rag.py (FINDINGS
#28): it fixes exact names ("punto de Surraco") but loses colloquial questions, and on held-out questions
it came out worse, so it isn't the default; it stays as an eval option to retry after re-chunking.
"""

import json
import threading

import numpy as np

from llm.gemini import MODELS, genai_client, with_rotation
from store import db

DIMS = 768  # gemini-embedding-001 truncated (Matryoshka); see rag/to_pgvector.py
MODO = "vector"  # "vector" | "hibrida"
CANDIDATES = 20  # chunks each ranking contributes to the fusion
RRF_K = 60  # the usual RRF constant: 1 / (RRF_K + rank)
LEXICAL_WEIGHT = 1.0  # BM25's share of the fusion (the vector ranking weighs 1)


def embed_query(text: str) -> list[float]:
    def call(key: str, model: str) -> list[float]:
        from google.genai import types

        res = genai_client(key).models.embed_content(
            model=model, contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=DIMS),
        )
        v = np.array(res.embeddings[0].values)
        return (v / np.linalg.norm(v)).tolist()  # truncated embeddings must be re-normalized

    return with_rotation(call, "embedding")


def search(materia: str, pregunta: str, k: int = 5, tipo: str | None = None) -> list[dict]:
    """[{id, texto, metadata, score}] best first; score = cosine distance (lower = closer)."""
    return search_with(materia, pregunta, embed_query(pregunta), k, tipo)


def search_with(materia: str, pregunta: str, embedding: list[float], k: int = 5, tipo: str | None = None,
                modo: str | None = None) -> list[dict]:
    """`search` with the query already embedded (the retrieval eval caches the embeddings)."""
    if (modo or MODO) == "vector":
        return search_vector(materia, embedding, k, tipo)
    vector = search_vector(materia, embedding, CANDIDATES, tipo)
    lexical = lexical_index(materia).top(pregunta, CANDIDATES, tipo)
    fused = rrf([[c["id"] for c in vector], lexical], [1.0, LEXICAL_WEIGHT])[:k]
    by_id = {c["id"]: c for c in vector}
    if missing := [i for i in fused if i not in by_id]:
        by_id.update({c["id"]: c for c in _rows(materia, embedding, ids=missing)})
    return [by_id[i] for i in fused]


def rrf(rankings: list[list[str]], weights: list[float] | None = None) -> list[str]:
    """Reciprocal rank fusion: ids by the sum of weight / (RRF_K + rank) over the rankings they appear in."""
    score: dict[str, float] = {}
    for ranking, w in zip(rankings, weights or [1.0] * len(rankings)):
        for rank, i in enumerate(ranking, 1):
            score[i] = score.get(i, 0.0) + w / (RRF_K + rank)
    return sorted(score, key=lambda i: -score[i])


def search_vector(materia: str, embedding: list[float], k: int = 5, tipo: str | None = None) -> list[dict]:
    return _rows(materia, embedding, k=k, tipo=tipo)


def _rows(materia: str, embedding: list[float], k: int | None = None, tipo: str | None = None,
          ids: list[str] | None = None) -> list[dict]:
    """Chunks by cosine distance: the k nearest, or the given ids (with their distance)."""
    vec = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    where, params = ["materia IN (%s, 'general')"], [vec, materia]
    if tipo:
        where.append("tipo = %s")
        params.append(tipo)
    if ids:
        where.append("id = ANY(%s)")
        params.append(ids)
    sql = f"""SELECT id, texto, metadata, embedding <=> %s::vector AS score FROM rag_chunks
              WHERE {' AND '.join(where)} ORDER BY score"""
    if k:
        sql += " LIMIT %s"
        params.append(k)
    with db.pool().connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"id": i, "texto": t, "metadata": m if isinstance(m, dict) else json.loads(m), "score": float(s)}
            for i, t, m, s in rows]


_indexes: dict = {}
_lock = threading.Lock()


def lexical_index(materia: str):
    """The BM25 index of the subject's chunks, read from Postgres once per process."""
    from rag.lexical import BM25

    with _lock:
        if materia not in _indexes:
            with db.pool().connection() as conn:
                rows = conn.execute("SELECT id, texto, tipo FROM rag_chunks WHERE materia IN (%s, 'general')",
                                    [materia]).fetchall()
            _indexes[materia] = BM25([{"id": i, "texto": t, "tipo": tp} for i, t, tp in rows])
        return _indexes[materia]
