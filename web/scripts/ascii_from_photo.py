"""Convierte la foto de un paciente en el retrato ASCII de la vista "cara a cara".

Requiere Pillow y rembg (`pip install "rembg[cpu]"`; baja un modelo de ~170 MB la primera vez).

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

# rampa corta y ordenada, de liviano a denso: con 70 caracteres las letras (xvXJ…) generan
# textura en vez de luz y sombra y la cara no se lee
RAMP = " .:-=+*#%@"
CHAR_ASPECT = 0.5  # una celda monoespaciada es ~el doble de alta que ancha


def remove_background(img: Image.Image) -> Image.Image:
    """Recorta a la persona con un modelo de segmentación (rembg / U²-Net, corre local) y pone
    el fondo en negro. Probé antes con heurísticas de color y fallaban con fondos en degradé
    o ropa del mismo tono que el fondo."""
    from rembg import new_session, remove

    cut = remove(img, session=new_session("u2net_human_seg"))
    black = Image.new("RGB", img.size, "black")
    black.paste(cut, mask=cut.getchannel("A"))
    return black


def to_ascii(img: Image.Image, cols: int, alto: float = 0.78, gamma: float = 0.8) -> str:
    """alto: fracción de la figura que se conserva desde arriba (recorte a cabeza y hombros).
    gamma < 1 levanta los medios tonos, donde están los rasgos de la cara."""
    gray = ImageOps.grayscale(img)
    # recorte: todo lo que no es fondo negro
    bbox = gray.point(lambda v: 255 if v > 18 else 0).getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        gray = gray.crop((x0, y0, x1, y0 + int((y1 - y0) * alto)))
    person = gray.point(lambda v: 255 if v > 12 else 0)
    # ecualizar solo sobre la persona: si no, el fondo negro se come el rango y la cara queda plana
    gray = ImageOps.equalize(gray, mask=person)
    gray = gray.point(lambda v: round(255 * (v / 255) ** gamma))
    gray = Image.composite(gray, Image.new("L", gray.size, 0), person)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=120, threshold=3))  # define rasgos
    rows = max(1, round(cols * gray.height / gray.width * CHAR_ASPECT))
    small = gray.resize((cols, rows), Image.Resampling.LANCZOS)
    lines = []
    for y in range(rows):
        line = "".join(RAMP[small.getpixel((x, y)) * (len(RAMP) - 1) // 255] for x in range(cols))
        lines.append(line.rstrip())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto", type=Path)
    ap.add_argument("--cols", type=int, default=110)
    ap.add_argument("--fondo-negro", action="store_true", help="la foto ya tiene fondo negro: no recortar fondo")
    args = ap.parse_args()
    ap_img = Image.open(args.foto).convert("RGB")
    if not args.fondo_negro:
        ap_img = remove_background(ap_img)
        ap_img.save(args.foto.with_name(args.foto.stem + "-sin-fondo.png"))
    art = to_ascii(ap_img, args.cols)
    out = Path(__file__).resolve().parent.parent / "public" / "retratos" / f"{args.foto.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(art + "\n", encoding="utf-8")
    print(f"{out} ({len(art.splitlines())} líneas x {args.cols} columnas)")


if __name__ == "__main__":
    main()
