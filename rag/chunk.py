"""Divide el material limpio de una materia en chunks para el RAG.

Uso:
    python rag/chunk.py mpna

Lee:
    data/ecoe/<materia>/clean/**/*.md    apuntes (raíz), guías (guias/) y material de cátedra (catedra/)
    data/ecoe/<materia>/grillas/*.json   grillas de evaluación (una por chunk)
    data/ecoe/contexto-ecoe.md           contexto general del ECOE (común a todas las materias)
Escribe:
    data/ecoe/<materia>/chunks.jsonl

Usa los splitters de LangChain: MarkdownHeaderTextSplitter corta por encabezados y
RecursiveCharacterTextSplitter parte las secciones largas. Cada chunk lleva metadata
para filtrar y citar (materia, fuente, tipo, sección, página) y su texto empieza con
la ruta de encabezados para que el embedding tenga contexto.
"""

import json
import re
import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

ROOT = Path(__file__).resolve().parent.parent
CHUNK_SIZE = 1800  # ~450 tokens
CHUNK_OVERLAP = 150
MIN_CHARS = 200  # secciones más cortas se unen con la siguiente

HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4")]
PAGE = re.compile(r"<!-- p\. (\d+) -->")
COMMENT = re.compile(r"<!--.*?-->", re.S)

header_splitter = MarkdownHeaderTextSplitter(HEADERS, strip_headers=True)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n- ", "\n", ". ", " "],
)


def section_path(doc: Document) -> str:
    return " > ".join(doc.metadata[h] for _, h in HEADERS if h in doc.metadata)


def merge_short(sections: list[Document]) -> list[Document]:
    """Une secciones muy cortas (p. ej. un título con una línea) con la siguiente."""
    merged: list[Document] = []
    for doc in sections:
        prev = merged[-1] if merged else None
        if prev and len(COMMENT.sub("", prev.page_content).strip()) < MIN_CHARS:
            title = section_path(doc).split(" > ")[-1]
            prev.page_content += f"\n\n{title}\n\n{doc.page_content}"
            continue
        merged.append(doc)
    return merged


def chunk_markdown(path: Path, materia: str, tipo: str) -> list[dict]:
    sections = merge_short(header_splitter.split_text(path.read_text(encoding="utf-8")))

    chunks: list[dict] = []
    page = None  # última marca de página vista, en orden de lectura
    for section in sections:
        seccion = section_path(section)
        # el splitter une las líneas con "  \n": se recuperan los cortes de párrafo
        content = section.page_content.replace("  \n", "\n\n")
        for part in text_splitter.split_text(content):
            # la página del chunk es la marca que lo abre (si no hay texto antes) o la última vista
            first = PAGE.search(part)
            opens = first and not COMMENT.sub("", part[: first.start()]).strip()
            chunk_page = int(first.group(1)) if opens else page
            for m in PAGE.finditer(part):
                page = int(m.group(1))
            text = re.sub(r"\n{3,}", "\n\n", COMMENT.sub("", part)).strip()
            if not text:
                continue
            chunks.append(
                {
                    "id": f"{materia}/{path.stem}/{len(chunks):04d}",
                    "texto": f"{seccion or path.stem}\n\n{text}",
                    "metadata": {
                        "materia": materia,
                        "fuente": path.name,
                        "tipo": tipo,
                        "seccion": seccion,
                        "pagina": chunk_page,
                    },
                }
            )
    return chunks


def chunk_grilla(path: Path, materia: str) -> dict:
    g = json.loads(path.read_text(encoding="utf-8"))
    lines = [f"Grilla de evaluación ECOE — {g['titulo']}"]
    if g.get("unidad_tematica"):
        lines.append(f"Unidad temática {g['unidad_tematica']['numero']}: {g['unidad_tematica']['nombre']}")
    if g.get("motivo_consulta"):
        lines.append(f"Motivo de consulta: {g['motivo_consulta']}")
    for sec in g["secciones"]:
        lines.append(f"\n{sec['nombre']}:")
        lines.extend(f"- {item}" for item in sec["items"])
    return {
        "id": f"{materia}/grillas/{g['id']}",
        "texto": "\n".join(lines),
        "metadata": {
            "materia": materia,
            "fuente": g.get("fuente", {}).get("archivo", path.name),
            "tipo": "grilla",
            "seccion": g["titulo"],
            "pagina": (g.get("fuente", {}).get("paginas") or [None])[0],
            "grilla_id": g["id"],
        },
    }


def main():
    materia = sys.argv[1] if len(sys.argv) > 1 else "mpna"
    base = ROOT / "data" / "ecoe" / materia
    chunks: list[dict] = []

    contexto = ROOT / "data" / "ecoe" / "contexto-ecoe.md"
    if contexto.exists():
        chunks += chunk_markdown(contexto, "general", "contexto_ecoe")
    # la subcarpeta de clean/ define el tipo: guias/ -> guia, catedra/ -> clase, raíz -> apunte
    tipos = {"guias": "guia", "catedra": "clase"}
    for md in sorted((base / "clean").rglob("*.md")):
        sub = md.parent.relative_to(base / "clean").as_posix()
        chunks += chunk_markdown(md, materia, tipos.get(sub, "apunte"))
    for gj in sorted((base / "grillas").glob("*.json")):
        if gj.name != "index.json":
            chunks.append(chunk_grilla(gj, materia))

    out = base / "chunks.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    by_source: dict[str, int] = {}
    for c in chunks:
        by_source[c["metadata"]["fuente"]] = by_source.get(c["metadata"]["fuente"], 0) + 1
    print(f"{len(chunks)} chunks -> {out.relative_to(ROOT)}")
    for src, n in sorted(by_source.items()):
        print(f"  {n:4d}  {src}")


if __name__ == "__main__":
    main()
