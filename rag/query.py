"""Consulta rápida al índice para probar el RAG.

Uso:
    python rag/query.py mpna "¿qué preguntar ante un dolor torácico?"
    python rag/query.py mpna "grilla disnea" --tipo grilla
"""

import argparse

from dotenv import load_dotenv

from ingest import ROOT, get_store


def main():
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("materia")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--tipo", choices=["apunte", "grilla", "contexto_ecoe"])
    args = p.parse_args()

    store = get_store(args.materia)
    where = {"tipo": args.tipo} if args.tipo else None
    for doc, score in store.similarity_search_with_score(args.pregunta, k=args.k, filter=where):
        m = doc.metadata
        print(f"[{score:.3f}] {m['fuente']} p.{m.get('pagina', '?')} — {m.get('seccion', '')}")
        print("   " + doc.page_content[:300].replace("\n", " ") + "…\n")


if __name__ == "__main__":
    main()
