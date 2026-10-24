"""Indexa los chunks de una materia en Chroma con embeddings de Gemini.

Uso:
    python rag/chunk.py mpna      # primero generar los chunks
    python rag/ingest.py mpna

Requiere GOOGLE_API_KEY en el entorno (o en .env).
El índice queda en .chroma/ (no se versiona) con una colección por materia: ecoe_<materia>.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

ROOT = Path(__file__).resolve().parent.parent
PERSIST_DIR = ROOT / ".chroma"
EMBEDDING_MODEL = "models/gemini-embedding-001"
BATCH = 50


def get_store(materia: str) -> Chroma:
    return Chroma(
        collection_name=f"ecoe_{materia}",
        embedding_function=GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL),
        persist_directory=str(PERSIST_DIR),
    )


def main():
    load_dotenv(ROOT / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit("Falta GOOGLE_API_KEY (ponla en .env)")

    materia = sys.argv[1] if len(sys.argv) > 1 else "mpna"
    path = ROOT / "data" / "ecoe" / materia / "chunks.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    store = get_store(materia)
    store.reset_collection()
    for i in range(0, len(rows), BATCH):
        batch = rows[i : i + BATCH]
        docs = [
            # Chroma no acepta None en metadata
            Document(page_content=r["texto"], metadata={k: v for k, v in r["metadata"].items() if v is not None})
            for r in batch
        ]
        store.add_documents(docs, ids=[r["id"] for r in batch])
        print(f"{min(i + BATCH, len(rows))}/{len(rows)}")
    print(f"Listo: colección ecoe_{materia} en {PERSIST_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
