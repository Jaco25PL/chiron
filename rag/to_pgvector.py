"""Copies the RAG index from Chroma to Postgres (pgvector) without re-embedding.

Usage:
    python rag/to_pgvector.py mpna            # copy from Chroma
    python rag/to_pgvector.py mpna --missing  # embed chunks.jsonl rows missing from rag_chunks

gemini-embedding-001 vectors are Matryoshka embeddings: their first 768 dimensions,
re-normalized, work as a 768-dim embedding (top-5 overlap with 3072 dims was 28/30 on a
sample of queries). So the existing 3072-dim vectors are truncated instead of paying for
new embedding calls.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rag.search import DIMS  # noqa: E402
from store import db  # noqa: E402


def main():
    import chromadb

    materia = sys.argv[1] if len(sys.argv) > 1 else "mpna"
    col = chromadb.PersistentClient(path=str(ROOT / ".chroma")).get_collection(f"ecoe_{materia}")
    r = col.get(include=["embeddings", "documents", "metadatas"])
    vecs = np.array(r["embeddings"])[:, :DIMS]
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

    rows = [
        (cid, m.get("materia", materia), m.get("tipo", "apunte"), m.get("fuente", ""), m.get("seccion"),
         m.get("pagina"), doc, json.dumps(m, ensure_ascii=False), "[" + ",".join(f"{x:.6f}" for x in v) + "]")
        for cid, doc, m, v in zip(r["ids"], r["documents"], r["metadatas"], vecs)
    ]
    with db.pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM rag_chunks WHERE materia IN (%s, 'general')", (materia,))
        cur.executemany(
            """INSERT INTO rag_chunks (id, materia, tipo, fuente, seccion, pagina, texto, metadata, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
               ON CONFLICT (id) DO UPDATE SET texto = EXCLUDED.texto, metadata = EXCLUDED.metadata,
                 embedding = EXCLUDED.embedding""",
            rows,
        )
    print(f"{len(rows)} chunks -> rag_chunks ({DIMS} dims)")


def fill_missing(materia: str, batch: int = 20):
    """Embeds (768 dims) every chunk in chunks.jsonl that rag_chunks doesn't have yet."""
    from google import genai
    from google.genai import types

    from llm.gemini import with_rotation

    rows = [json.loads(l) for l in (ROOT / "data" / "ecoe" / materia / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    with db.pool().connection() as conn:
        have = {r[0] for r in conn.execute("SELECT id FROM rag_chunks").fetchall()}
    missing = [r for r in rows if r["id"] not in have]
    print(f"{len(missing)} missing")
    for i in range(0, len(missing), batch):
        part = missing[i : i + batch]

        def call(key, model):
            client = genai.Client(api_key=key)  # keep a reference: an inline client gets closed before the call
            res = client.models.embed_content(
                model=model, contents=[r["texto"] for r in part],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=DIMS),
            )
            return [np.array(e.values) for e in res.embeddings]

        vecs = with_rotation(call, "embedding")
        with db.pool().connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO rag_chunks (id, materia, tipo, fuente, seccion, pagina, texto, metadata, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector) ON CONFLICT (id) DO NOTHING""",
                [(r["id"], r["metadata"].get("materia", materia), r["metadata"]["tipo"], r["metadata"]["fuente"],
                  r["metadata"].get("seccion"), r["metadata"].get("pagina"), r["texto"],
                  json.dumps(r["metadata"], ensure_ascii=False),
                  "[" + ",".join(f"{x:.6f}" for x in v / np.linalg.norm(v)) + "]") for r, v in zip(part, vecs)],
            )
        print(f"  {min(i + batch, len(missing))}/{len(missing)}")


if __name__ == "__main__":
    if "--missing" in sys.argv:
        fill_missing(sys.argv[1] if len(sys.argv) > 2 else "mpna")
    else:
        main()
