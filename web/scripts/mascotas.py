"""Builds the study companion's pets (web/public/mascotas/<slug>.webp) from Petdex downloads.

Usage:
    python web/scripts/mascotas.py <dir with Petdex zips: <slug>/<slug>.zip or <slug>.zip>

Petdex (https://petdex.dev) sheets are 192x208 cells, one animation per row in a fixed order. We keep
only the rows the app uses (web/lib/mascotas.ts ANIMACIONES, same order) and scale them to 2/3 (each
cell 128x139: crisp at the ~70 px the pet is shown, on 2x screens), which takes a 1.5-3 MB sheet down
to a few hundred KB. Only pets whose author declared a license that allows reuse (CC0, CC-BY or
CC-BY-SA; treat them as CC-BY-SA) may be added: credit them in web/lib/mascotas.ts.
"""

import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "public" / "mascotas"
CELL = (192, 208)
SCALE = 2 / 3
# Petdex row order: idle, running-right, running-left, waving, jumping, failed, waiting, running, review
ROWS = {"idle": (0, 6), "waving": (3, 4), "review": (8, 6), "jumping": (4, 5), "waiting": (6, 6)}


def build(zip_path: Path) -> Path:
    slug = zip_path.stem
    with zipfile.ZipFile(zip_path) as z:
        sheet = Image.open(io.BytesIO(z.read("spritesheet.webp"))).convert("RGBA")
    w, h = round(CELL[0] * SCALE), round(CELL[1] * SCALE)
    cols = max(n for _, n in ROWS.values())
    out = Image.new("RGBA", (cols * w, len(ROWS) * h))
    for i, (fila, frames) in enumerate(ROWS.values()):
        for f in range(frames):
            cell = sheet.crop((f * CELL[0], fila * CELL[1], (f + 1) * CELL[0], (fila + 1) * CELL[1]))
            out.paste(cell.resize((w, h), Image.LANCZOS), (f * w, i * h))
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{slug}.webp"
    out.save(dest, "WEBP", quality=88, method=6)
    return dest


def main():
    src = Path(sys.argv[1])
    for z in sorted(src.glob("**/*.zip")):
        dest = build(z)
        print(f"{dest.name}: {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
