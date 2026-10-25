"""Generates the patient's static ASCII portrait (placeholder until there is a real avatar).

Models a bust as a height map (sum of ellipsoids), lights it with a directional
light and maps luminance to characters. Usage:
    python scripts/ascii_face.py > lib/ascii-face.txt
"""
import math

W, H = 76, 44
RAMP = " .,:;-~=+*!?%#&$@"
LIGHT = (-0.45, -0.55, 0.70)


def ell(u, v, cx, cy, rx, ry, h):
    d = ((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2
    return h * math.sqrt(1 - d) if d < 1 else None


def bump(u, v, cx, cy, rx, ry):
    return math.exp(-(((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2))


def height(u, v):
    parts = []
    head = ell(u, v, 0, -0.16, 0.47, 0.54, 1.0)
    neck = ell(u, v, 0, 0.50, 0.19, 0.30, 0.55)
    shoulders = ell(u, v, 0, 1.18, 0.98, 0.50, 0.65)
    ears = [ell(u, v, sx * 0.47, -0.10, 0.06, 0.12, 0.6) for sx in (-1, 1)]
    for p in (head, neck, shoulders, *ears):
        if p is not None:
            parts.append(p)
    if not parts:
        return None
    h = max(parts)
    if head is not None:
        for cx, cy, rx, ry, dh in [
            (-0.17, -0.19, 0.085, 0.045, -0.28),  # eye sockets
            (0.17, -0.19, 0.085, 0.045, -0.28),
            (-0.17, -0.27, 0.11, 0.025, 0.10),    # eyebrows
            (0.17, -0.27, 0.11, 0.025, 0.10),
            (0.0, -0.07, 0.045, 0.13, 0.22),      # nose
            (0.0, 0.03, 0.07, 0.035, 0.10),       # nose tip
            (-0.27, 0.00, 0.10, 0.09, 0.07),      # cheekbones
            (0.27, 0.00, 0.10, 0.09, 0.07),
            (0.0, 0.155, 0.12, 0.025, 0.07),      # lips
            (0.0, 0.18, 0.09, 0.010, -0.07),      # mouth
            (0.0, 0.29, 0.13, 0.06, 0.06),        # chin
            (-0.36, 0.10, 0.10, 0.20, -0.08),     # cheeks toward the jaw
            (0.36, 0.10, 0.10, 0.20, -0.08),
        ]:
            h += dh * bump(u, v, cx, cy, rx, ry)
    return h


def albedo(u, v):
    """Surface color: darker hair, eyes and mouth (soft edges)."""
    a = 1.0
    hairline = -0.36 + 0.22 * (abs(u) / 0.47) ** 3
    in_head = (u / 0.49) ** 2 + ((v + 0.17) / 0.56) ** 2 < 1
    if in_head:
        t = 1 / (1 + math.exp((v - hairline) / 0.015))  # 1 = hair
        a *= 1 - 0.62 * t * (0.75 + 0.25 * math.sin(u * 55 + v * 12))
    for sx in (-1, 1):
        a *= 1 - 0.75 * bump(u, v, sx * 0.17, -0.19, 0.055, 0.022)  # iris
        a *= 1 + 0.9 * bump(u, v, sx * 0.17 - 0.015, -0.198, 0.012, 0.008)  # highlight
    a *= 1 - 0.55 * bump(u, v, 0, 0.18, 0.085, 0.009)  # mouth
    a *= 1 - 0.35 * bump(u, v, 0, 0.02, 0.03, 0.012)   # nostrils
    return a


def shade(u, v, light):
    h = height(u, v)
    if h is None:
        return None
    eps = 0.006
    hx, hy = height(u + eps, v), height(u, v + eps)
    dx = ((hx if hx is not None else 0) - h) / eps
    dy = ((hy if hy is not None else 0) - h) / eps
    nx, ny, nz = -dx, -dy, 1.0
    m = math.sqrt(nx * nx + ny * ny + nz * nz)
    lx, ly, lz = light
    diff = max(0.0, (nx * lx + ny * ly + nz * lz) / m)
    lum = (0.10 + 0.90 * diff ** 1.3) * albedo(u, v)
    return lum * (0.55 + 0.45 * min(1.0, h / 0.6))


def main():
    lx, ly, lz = (-0.30, -0.45, 0.84)
    n = math.sqrt(lx * lx + ly * ly + lz * lz)
    light = (lx / n, ly / n, lz / n)
    SS = 3  # supersampling per cell
    rows = []
    for j in range(H):
        row = []
        for i in range(W):
            vals, hits = 0.0, 0
            for a in range(SS):
                for b in range(SS):
                    u = ((i + (a + 0.5) / SS) / W) * 2 - 1
                    v = ((j + (b + 0.5) / SS) / H) * 2.1 - 0.95
                    l = shade(u, v, light)
                    if l is not None:
                        vals += l
                        hits += 1
            if hits < SS * SS / 2:
                row.append(" ")
                continue
            lum = min(1.0, vals / hits)
            row.append(RAMP[min(len(RAMP) - 1, int(lum * (len(RAMP) - 1)))])
        rows.append("".join(row).rstrip())
    print("\n".join(rows))


if __name__ == "__main__":
    main()
