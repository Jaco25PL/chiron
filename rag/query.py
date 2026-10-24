"""Búsqueda en el índice del RAG.

Uso como script:
    python rag/query.py mpna "¿qué preguntar ante un dolor torácico?"
    python rag/query.py mpna "grilla disnea" --tipo grilla

Uso como módulo:
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
    """Devuelve [{texto, metadata, score}] ordenado por relevancia (menor score = más cercano)."""
    if materia not in _stores:
        _stores[materia] = get_store(materia)
    where = {"tipo": tipo} if tipo else None
    results = _stores[materia].similarity_search_with_score(pregunta, k=k, filter=where)
    return [{"texto": doc.page_content, "metadata": doc.metadata, "score": score} for doc, score in results]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("materia")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--tipo", choices=["apunte", "grilla", "contexto_ecoe"])
    args = p.parse_args()

    for r in search(args.materia, args.pregunta, args.k, args.tipo):
        m = r["metadata"]
        print(f"[{r['score']:.3f}] {m['fuente']} p.{m.get('pagina', '?')} — {m.get('seccion', '')}")
        print("   " + r["texto"][:300].replace("\n", " ") + "…\n")


if __name__ == "__main__":
    main()
