"""Indexes a subject's (materia) chunks into Chroma with Gemini embeddings.

Usage:
    python rag/chunk.py mpna      # generate the chunks first
    python rag/ingest.py mpna

Keys are read from .env (GOOGLE_API_KEY_1, _2, ...); if one runs out of quota,
it rotates to the next. The index lives in .chroma/ (not versioned), with one
collection per subject: ecoe_<materia>.
"""

import json
import sys
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from llm.gemini import MODELS, api_keys, with_rotation  # noqa: E402

PERSIST_DIR = ROOT / ".chroma"
BATCH = 50


def get_store(materia: str, api_key: str | None = None, model: str | None = None) -> Chroma:
    embeddings = GoogleGenerativeAIEmbeddings(
        model=model or MODELS["embedding"][0],
        google_api_key=api_key or api_keys()[0],
    )
    return Chroma(
        collection_name=f"ecoe_{materia}",
        embedding_function=embeddings,
        persist_directory=str(PERSIST_DIR),
    )


def main():
    materia = sys.argv[1] if len(sys.argv) > 1 else "mpna"
    path = ROOT / "data" / "ecoe" / materia / "chunks.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    get_store(materia).reset_collection()
    for i in range(0, len(rows), BATCH):
        batch = rows[i : i + BATCH]
        docs = [
            # Chroma doesn't accept None in metadata
            Document(page_content=r["texto"], metadata={k: v for k, v in r["metadata"].items() if v is not None})
            for r in batch
        ]
        ids = [r["id"] for r in batch]
        with_rotation(lambda key, model: get_store(materia, key, model).add_documents(docs, ids=ids), "embedding")
        print(f"{min(i + BATCH, len(rows))}/{len(rows)}")
    print(f"Done: collection ecoe_{materia} in {PERSIST_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
