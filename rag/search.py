"""RAG retrieval over Postgres + pgvector (the server's search path; no Chroma needed).

    from rag.search import search
    search("mpna", "¿cuándo pedir urocultivo?", k=5, tipo="clase")
"""

import json

import numpy as np

from llm.gemini import MODELS, with_rotation
from store import db

DIMS = 768  # gemini-embedding-001 truncated (Matryoshka); see rag/to_pgvector.py


def embed_query(text: str) -> list[float]:
    def call(key: str, model: str) -> list[float]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        res = client.models.embed_content(
            model=model, contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=DIMS),
        )
        v = np.array(res.embeddings[0].values)
        return (v / np.linalg.norm(v)).tolist()  # truncated embeddings must be re-normalized

    return with_rotation(call, "embedding")


def search(materia: str, pregunta: str, k: int = 5, tipo: str | None = None) -> list[dict]:
    """[{texto, metadata, score}] by cosine distance (lower = closer), like the Chroma version."""
    vec = "[" + ",".join(f"{x:.6f}" for x in embed_query(pregunta)) + "]"
    sql = """SELECT texto, metadata, embedding <=> %s::vector AS score FROM rag_chunks
             WHERE materia IN (%s, 'general') {tipo} ORDER BY score LIMIT %s"""
    params: list = [vec, materia]
    if tipo:
        params.append(tipo)
    params.append(k)
    with db.pool().connection() as conn:
        rows = conn.execute(sql.format(tipo="AND tipo = %s" if tipo else ""), params).fetchall()
    return [{"texto": t, "metadata": m if isinstance(m, dict) else json.loads(m), "score": float(s)} for t, m, s in rows]
