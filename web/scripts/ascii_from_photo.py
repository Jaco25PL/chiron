"""Convierte la foto de un paciente en el retrato ASCII de la vista "cara a cara".

Uso:
    python scripts/ascii_from_photo.py scripts/retratos/<case_id>.png [--cols 110]

Escribe public/retratos/<case_id>.txt, que el front carga por caso.

Sigue las recomendaciones de generadores como ScreenSnap/ASCIIFY:
- foto de frente, con alto contraste y fondo negro (el fondo se recorta solo);
- recorte ajustado a la cabeza y los hombros;
- más columnas = más detalle;
- caracteres densos para las zonas claras (la UI es oscura) y livianos para las oscuras.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

# rampa de 70 niveles (Paul Bourke), de más denso a más liviano; se invierte para fondo oscuro
RAMP = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
CHAR_ASPECT = 0.5  # una celda monoespaciada es ~el doble de alta que ancha


def to_ascii(img: Image.Image, cols: int) -> str:
    gray = ImageOps.grayscale(img)
    # recorte: todo lo que no es fondo negro
    bbox = gray.point(lambda v: 255 if v > 18 else 0).getbbox()
    if bbox:
        gray = gray.crop(bbox)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2))  # define rasgos
    rows = max(1, round(cols * gray.height / gray.width * CHAR_ASPECT))
    small = gray.resize((cols, rows), Image.Resampling.LANCZOS)
    ramp = RAMP[::-1]  # claro -> denso
    lines = []
    for y in range(rows):
        line = "".join(ramp[small.getpixel((x, y)) * (len(ramp) - 1) // 255] for x in range(cols))
        lines.append(line.rstrip())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto", type=Path)
    ap.add_argument("--cols", type=int, default=110)
    args = ap.parse_args()
    art = to_ascii(Image.open(args.foto).convert("RGB"), args.cols)
    out = Path(__file__).resolve().parent.parent / "public" / "retratos" / f"{args.foto.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(art + "\n", encoding="utf-8")
    print(f"{out} ({len(art.splitlines())} líneas x {args.cols} columnas)")


if __name__ == "__main__":
    main()
