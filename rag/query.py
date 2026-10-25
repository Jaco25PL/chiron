"""Search over the RAG index.

As a script:
    python rag/query.py mpna "¿qué preguntar ante un dolor torácico?"
    python rag/query.py mpna "grilla disnea" --tipo grilla

As a module:
    from rag.query import search
    search("mpna", "disuria", k=5, tipo="grilla")
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rag.ingest import get_store  # noqa: E402

_stores = {}


def search(materia: str, pregunta: str, k: int = 5, tipo: str | None = None) -> list[dict]:
    """Returns [{texto, metadata, score}] sorted by relevance (lower score = closer)."""
    if materia not in _stores:
        _stores[materia] = get_store(materia)
    where = {"tipo": tipo} if tipo else None
    results = _stores[materia].similarity_search_with_score(pregunta, k=k, filter=where)
    return [{"texto": doc.page_content, "metadata": doc.metadata, "score": score} for doc, score in results]


def main():
    p = argparse.ArgumentParser(description="Search the RAG index of a subject (materia).")
    p.add_argument("materia", help="subject, e.g. mpna")
    p.add_argument("pregunta", help="query text (in Spanish, like the indexed material)")
    p.add_argument("-k", type=int, default=5, help="number of results")
    p.add_argument("--tipo", choices=["apunte", "guia", "clase", "grilla", "contexto_ecoe"], help="filter by source type")
    args = p.parse_args()

    for r in search(args.materia, args.pregunta, args.k, args.tipo):
        m = r["metadata"]
        print(f"[{r['score']:.3f}] {m['fuente']} p.{m.get('pagina', '?')} — {m.get('seccion', '')}")
        print("   " + r["texto"][:300].replace("\n", " ") + "…\n")


if __name__ == "__main__":
    main()
