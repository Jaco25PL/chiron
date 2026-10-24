"""Divide el material limpio de una materia en chunks para el RAG.

Uso:
    python rag/chunk.py mpna

Lee:
    data/ecoe/<materia>/clean/*.md   apuntes en Markdown
    data/ecoe/<materia>/grillas/*.json   grillas de evaluación (una por chunk)
    data/ecoe/contexto-ecoe.md       contexto general del ECOE (común a todas las materias)
Escribe:
    data/ecoe/<materia>/chunks.jsonl

Cada chunk lleva metadata para filtrar y citar: materia, fuente, tipo, sección
(ruta de encabezados) y página. El texto de cada chunk empieza con la ruta de
encabezados para que el embedding tenga contexto.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_CHARS = 1800  # ~450 tokens
MIN_CHARS = 200

HEADING = re.compile(r"^(#{1,4}) (.+)$")
PAGE = re.compile(r"^<!-- p\. (\d+) -->$")


def split_long(text: str) -> list[str]:
    """Parte un bloque largo por párrafos, sin cortar a mitad de párrafo."""
    parts, current = [], ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) > MAX_CHARS:
            parts.append(current.strip())
            current = ""
        current += para + "\n\n"
    if current.strip():
        parts.append(current.strip())
    return parts


def chunk_markdown(path: Path, materia: str, tipo: str) -> list[dict]:
    headings: list[str] = []
    page = None
    sections: list[dict] = []
    body: list[str] = []
    body_page = None

    def flush():
        text = "\n".join(body).strip()
        if text:
            sections.append({"seccion": " > ".join(headings), "pagina": body_page, "texto": text})
        body.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        if m := PAGE.match(line):
            page = int(m.group(1))
            continue
        if line.startswith("<!--"):
            continue
        if m := HEADING.match(line):
            flush()
            level = len(m.group(1))
            headings[:] = headings[: level - 1] + [m.group(2).strip()]
            continue
        if not body:
            body_page = page
        body.append(line)
    flush()

    # une secciones muy cortas con la siguiente y parte las largas
    merged: list[dict] = []
    for s in sections:
        if merged and len(merged[-1]["texto"]) < MIN_CHARS:
            prev = merged[-1]
            prev["texto"] += f"\n\n{s['seccion'].split(' > ')[-1]}\n\n{s['texto']}"
            continue
        merged.append(s)

    chunks = []
    for s in merged:
        for i, part in enumerate(split_long(s["texto"])):
            header = s["seccion"] or path.stem
            chunks.append(
                {
                    "id": f"{materia}/{path.stem}/{len(chunks):04d}",
                    "texto": f"{header}\n\n{part}",
                    "metadata": {
                        "materia": materia,
                        "fuente": path.name,
                        "tipo": tipo,
                        "seccion": s["seccion"],
                        "pagina": s["pagina"],
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
    for md in sorted((base / "clean").glob("*.md")):
        chunks += chunk_markdown(md, materia, "apunte")
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
