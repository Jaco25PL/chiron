"""Extracts and cleans a subject's (materia) PDF course notes and saves them as Markdown.

Usage:
    python rag/clean_pdfs.py mpna

Reads data/ecoe/<materia>/raw/*.pdf and writes data/ecoe/<materia>/clean/<name>.md.
It also cleans the sources listed in data/ecoe/<materia>/sources.json (EVA material)
into clean/<out>, e.g. clean/guias/ or clean/catedra/.
Requires `pdftotext` (poppler) on the PATH.

Cleaning is deterministic (no LLM) so medical content is never altered:
- removes page numbers and marks each page with <!-- p. N --> for citations
- turns titles into Markdown headings
- joins broken lines into paragraphs and normalizes bullets
- keeps aligned tables in ```text blocks
- drops diagram leftovers (lines with almost no text)
"""

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Documents that aren't prose and are processed separately (grillas -> JSON, paraclínica -> table).
SKIP = {"grillas-mpna", "paraclinica"}

# "n" and private-use characters are bullets from symbol fonts (Wingdings) in slides
BULLET = re.compile(r"^\s*(?:[•●▪◦·-]|[-n](?=\s)|\d+[.)](?=\s))\s*")
PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
COLUMN_GAP = re.compile(r"\S {3,}\S")
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "​": ""}


def normalize(text: str) -> str:
    for bad, good in LIGATURES.items():
        text = text.replace(bad, good)
    # "ı́" (dotless i + combining accent) and similar -> precomposed form
    text = text.replace("ı́", "í")
    # Wingdings bullets: "n" + private-use character at line start -> "•"
    text = re.sub(r"(?m)^(\s*)n?[-]+[  ]*", r"\1• ", text)
    text = re.sub(r"[-]", "", text)
    return unicodedata.normalize("NFC", text)


def word_ratio(line: str) -> float:
    letters = sum(c.isalpha() for c in line)
    return letters / max(len(line.strip()), 1)


def has_word(line: str, min_len: int = 3) -> bool:
    return re.search(r"[^\W\d_]{%d,}" % min_len, line) is not None


def is_diagram_label(text: str) -> bool:
    """Stray diagram label ("+", "aVR", "V6"): no useful words or numbers."""
    return not has_word(text, 4) and not re.search(r"\d", text) and len(text) <= 15


def is_heading(line: str, prev_blank: bool) -> int:
    """Returns the heading level (0 if it isn't a heading)."""
    text = line.strip()
    if not text or len(text) > 70 or text.endswith((".", ",", ";", ":")) or BULLET.match(line):
        return 0
    if COLUMN_GAP.search(text) or word_ratio(text) < 0.6 or not has_word(text, 4):
        return 0
    if re.match(r"^MÓDULO\s+\d+", text):
        return 1
    indent = len(line) - len(line.lstrip())
    letters = [c for c in text if c.isalpha()]
    all_caps = len(letters) >= 4 and all(c.isupper() for c in letters)
    if all_caps and prev_blank:
        return 3
    if indent >= 5 and prev_blank and text[0].isupper():
        return 2
    return 0


def clean_page(raw: str) -> list[str]:
    lines = [normalize(l.rstrip()) for l in raw.split("\n")]
    lines = [l for l in lines if not PAGE_NUMBER.match(l) and "flexcil" not in l.lower()]
    out: list[str] = []
    paragraph: list[str] = []
    table: list[str] = []
    bullet_indent = -1  # indent of the open bullet (-1 if the paragraph isn't a bullet)

    def flush_paragraph():
        if paragraph:
            text = " ".join(paragraph)
            text = re.sub(r"(\w)- (\w)", r"\1\2", text)  # words hyphenated across lines
            out.append(re.sub(r"\s+", " ", text).strip())
            out.append("")
            paragraph.clear()

    def flush_table():
        if not table:
            return
        block = [l for l in table if l.strip()]
        words = sum(len(re.findall(r"[^\W\d_]{3,}", l)) for l in block)
        numbers = sum(len(re.findall(r"\d", l)) for l in block)
        # block with no words or values = diagram leftover: drop it
        if words >= 4 or numbers >= 3:
            indent = min(len(l) - len(l.lstrip()) for l in block)
            out.append("```text")
            out.extend(l[indent:] for l in block)
            out.append("```")
            out.append("")
        table.clear()

    for i, line in enumerate(lines):
        text = line.strip()
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        prev_blank = i == 0 or not lines[i - 1].strip()

        if not text:
            flush_paragraph()
            if table:
                table.append("")
            continue

        if COLUMN_GAP.search(text) and not BULLET.match(line):
            flush_paragraph()
            table.append(line)
            continue
        if not BULLET.match(line) and is_diagram_label(text):
            continue
        if table:
            # a short line between table rows is usually part of the table
            if len(text) < 30 and next_line.strip() and COLUMN_GAP.search(next_line.strip()):
                table.append(line)
                continue
            flush_table()

        level = is_heading(line, prev_blank)
        if level:
            flush_paragraph()
            out.append("#" * level + " " + (text.capitalize() if level == 3 else text))
            out.append("")
            continue

        indent = len(line) - len(line.lstrip())
        if BULLET.match(line):
            flush_paragraph()
            paragraph.append("- " + BULLET.sub("", line, count=1).strip())
            bullet_indent = indent
            continue
        # text indented less than the open bullet: the list ends
        if paragraph and bullet_indent >= 0 and indent <= bullet_indent:
            flush_paragraph()
        if not paragraph:
            bullet_indent = -1

        # short subtitle-like line ("Plano frontal") before a paragraph
        if (
            not paragraph
            and len(text.split()) <= 6
            and text[0].isupper()
            and has_word(text, 4)
            and not text.endswith((".", ",", ";"))
            and next_line.strip()
            and not BULLET.match(next_line)
        ):
            out.append(f"**{text.rstrip(':')}**")
            out.append("")
            continue

        # paragraph or bullet continuation
        if paragraph and paragraph[-1].rstrip().endswith((".", ":")) and text[0].isupper():
            flush_paragraph()
        paragraph.append(text)

    flush_paragraph()
    flush_table()
    return out


def pdf_to_markdown(pdf: Path, layout: bool = True) -> str:
    """layout=False uses pdftotext's reading order: better for two-column PDFs."""
    raw = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", *(["-layout"] if layout else []), str(pdf), "-"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    pages = raw.split("\f")
    md = [f"<!-- fuente: {pdf.name} -->", ""]
    for n, page in enumerate(pages, start=1):
        body = clean_page(page)
        if any(l.strip() for l in body):
            md.append(f"<!-- p. {n} -->")
            md.append("")
            md.extend(body)
    text = "\n".join(md)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?m)^(- .*)\n\n(?=- )", r"\1\n", text)  # lists without blank lines
    return text.strip() + "\n"


def main():
    materia = sys.argv[1] if len(sys.argv) > 1 else "mpna"
    raw_dir = ROOT / "data" / "ecoe" / materia / "raw"
    clean_dir = ROOT / "data" / "ecoe" / materia / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(pdf, clean_dir / f"{pdf.stem}.md", True) for pdf in sorted(raw_dir.glob("*.pdf")) if pdf.stem not in SKIP]
    manifest = ROOT / "data" / "ecoe" / materia / "sources.json"
    if manifest.exists():
        jobs += [
            (raw_dir / s["raw"], clean_dir / s["out"], s.get("layout", True))
            for s in json.loads(manifest.read_text(encoding="utf-8"))["sources"]
        ]
    for pdf, out, layout in jobs:
        if not pdf.exists():
            print(f"MISSING {pdf.relative_to(ROOT)} (skipped)")
            continue
        md = pdf_to_markdown(pdf, layout)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"{pdf.name} -> {out.relative_to(ROOT)} ({len(md):,} chars)")


if __name__ == "__main__":
    main()
