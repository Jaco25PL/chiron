"""Turns a patient photo into the ASCII portrait for the "face to face" view.

Requires Pillow and rembg (`pip install "rembg[cpu]"`; downloads a ~170 MB model the first time).

Usage:
    python scripts/ascii_from_photo.py scripts/retratos/<case_id>.png [--cols 110]

Writes public/retratos/<case_id>.txt, which the frontend loads per case.

Follows the recommendations of generators like ScreenSnap/ASCIIFY:
- front-facing photo, high contrast, black background (the background is removed automatically);
- tight crop to the head and shoulders;
- more columns = more detail;
- dense characters for light areas (the UI is dark) and light characters for dark areas.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

# short, ordered ramp from light to dense: with 70 characters the letters (xvXJ…) create
# texture instead of light and shadow, and the face becomes unreadable
RAMP = " .:-=+*#%@"
CHAR_ASPECT = 0.5  # a monospace cell is ~twice as tall as it is wide


def remove_background(img: Image.Image, modelo: str = "u2net_human_seg") -> Image.Image:
    """Cuts out the person with a segmentation model (rembg / U²-Net, runs locally) and makes
    the background black. I tried color heuristics first, and they failed with gradient
    backgrounds or clothing the same tone as the background."""
    from rembg import new_session, remove

    cut = remove(img, session=new_session(modelo))
    black = Image.new("RGB", img.size, "black")
    black.paste(cut, mask=cut.getchannel("A"))
    return black


def to_ascii(img: Image.Image, cols: int, alto: float = 0.78, gamma: float = 0.8, plano: bool = False) -> str:
    """alto: fraction of the figure kept from the top (crop to head and shoulders).
    gamma < 1 lifts the midtones, where the facial features are.
    plano=True for flat-color illustrations: no equalizing or sharpening (they ruin them)."""
    gray = ImageOps.grayscale(img)
    # crop: everything that isn't black background
    bbox = gray.point(lambda v: 255 if v > 18 else 0).getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        gray = gray.crop((x0, y0, x1, y0 + int((y1 - y0) * alto)))
    person = gray.point(lambda v: 255 if v > 12 else 0)
    # equalize only over the person: otherwise the black background eats the range and the face looks flat
    if not plano:
        gray = ImageOps.equalize(gray, mask=person)
        gray = gray.point(lambda v: round(255 * (v / 255) ** gamma))
    gray = Image.composite(gray, Image.new("L", gray.size, 0), person)
    if not plano:
        gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=120, threshold=3))  # sharpens features
    rows = max(1, round(cols * gray.height / gray.width * CHAR_ASPECT))
    small = gray.resize((cols, rows), Image.Resampling.LANCZOS)
    lines = []
    for y in range(rows):
        line = "".join(RAMP[small.getpixel((x, y)) * (len(RAMP) - 1) // 255] for x in range(cols))
        lines.append(line.rstrip())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Convert a patient photo into an ASCII portrait.")
    ap.add_argument("foto", type=Path, help="input photo")
    ap.add_argument("--cols", type=int, default=110, help="output width in characters")
    ap.add_argument("--alto", type=float, default=0.78, help="fraction of the figure to keep from the top")
    ap.add_argument("--modelo", default="u2net_human_seg", help="rembg model (u2net for non-people)")
    ap.add_argument("--plano", action="store_true", help="flat-color illustration (not a photo)")
    ap.add_argument("--fondo-negro", action="store_true", help="the photo already has a black background: skip background removal")
    args = ap.parse_args()
    ap_img = Image.open(args.foto).convert("RGB")
    if not args.fondo_negro:
        ap_img = remove_background(ap_img, args.modelo)
        ap_img.save(args.foto.with_name(args.foto.stem + "-sin-fondo.png"))
    art = to_ascii(ap_img, args.cols, alto=args.alto, plano=args.plano)
    out = Path(__file__).resolve().parent.parent / "public" / "retratos" / f"{args.foto.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(art + "\n", encoding="utf-8")
    print(f"{out} ({len(art.splitlines())} lines x {args.cols} columns)")


if __name__ == "__main__":
    main()
