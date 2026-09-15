"""Trei concepte complet diferite de iconita, pentru comparatie vizuala.

A - Teren vazut de sus: geometrie pura, fara minge. Sobru, foarte lizibil mic.
B - Minge singura, mare: simbolul clasic, fara ornamente.
C - Traiectorie ascendenta cu minge: accentul cade pe analiza, nu pe fotbal.

Fiecare se randeaza si patrat, si decupat rotund, ca sa se vada cum arata efectiv
pe telefon.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent.parent / "app" / "assets" / "icon" / "optiuni"
SIZE = 512
SS = 4
S = SIZE * SS

INDIGO_HI = (79, 70, 229)
INDIGO_LO = (49, 46, 129)
NIGHT_HI = (30, 27, 75)
NIGHT_LO = (9, 12, 22)
WHITE = (245, 247, 252)
AMBER = (251, 191, 36)
DARK = (11, 15, 26)


def gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        e = (y / (size - 1)) ** 1.2
        row = tuple(round(top[i] + (bottom[i] - top[i]) * e) for i in range(3))
        for x in range(size):
            px[x, y] = row
    return img


def pentagon(c: float, r: float, rotation: float = 0.0) -> list[tuple[float, float]]:
    return [
        (c + r * math.sin(math.radians(72 * i + rotation)),
         c - r * math.cos(math.radians(72 * i + rotation)))
        for i in range(5)
    ]


def ball(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
         body=WHITE, ink=DARK) -> None:
    """Mingea clasica: cerc, pentagon central, cinci cusaturi pana la margine."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=body)
    r_pent = r * 0.40
    pts = [
        (cx + r_pent * math.sin(math.radians(72 * i)),
         cy - r_pent * math.cos(math.radians(72 * i)))
        for i in range(5)
    ]
    draw.polygon(pts, fill=ink)
    width = max(1, round(r * 0.095))
    for i in range(5):
        a = math.radians(72 * i)
        draw.line(
            [(cx + r_pent * 0.96 * math.sin(a), cy - r_pent * 0.96 * math.cos(a)),
             (cx + r * math.sin(a), cy - r * math.cos(a))],
            fill=ink, width=width,
        )


def concept_pitch(size: int) -> Image.Image:
    """A — terenul vazut de sus."""
    img = gradient(size, INDIGO_HI, INDIGO_LO).convert("RGBA")
    d = ImageDraw.Draw(img)
    lw = round(size * 0.020)
    left, right = size * 0.19, size * 0.81
    top, bottom = size * 0.13, size * 0.87
    mid_y = size * 0.5

    d.rounded_rectangle([left, top, right, bottom], radius=size * 0.02,
                        outline=WHITE, width=lw)
    d.line([(left, mid_y), (right, mid_y)], fill=WHITE, width=lw)
    r_c = size * 0.115
    d.ellipse([size / 2 - r_c, mid_y - r_c, size / 2 + r_c, mid_y + r_c],
              outline=WHITE, width=lw)
    r_s = size * 0.017
    d.ellipse([size / 2 - r_s, mid_y - r_s, size / 2 + r_s, mid_y + r_s], fill=WHITE)

    box_w, box_h = size * 0.34, size * 0.105
    for y0, y1 in ((top, top + box_h), (bottom - box_h, bottom)):
        d.rectangle([size / 2 - box_w / 2, y0, size / 2 + box_w / 2, y1],
                    outline=WHITE, width=lw)
    return img


def concept_ball(size: int) -> Image.Image:
    """B — mingea singura, mare."""
    img = gradient(size, INDIGO_HI, INDIGO_LO).convert("RGBA")
    ball(ImageDraw.Draw(img), size / 2, size / 2, size * 0.325)
    return img


def concept_trend(size: int) -> Image.Image:
    """C — traiectorie ascendenta, cu mingea in varf."""
    img = gradient(size, NIGHT_HI, NIGHT_LO).convert("RGBA")
    d = ImageDraw.Draw(img)

    pts = [(size * 0.17, size * 0.76), (size * 0.38, size * 0.60),
           (size * 0.55, size * 0.66), (size * 0.76, size * 0.33)]
    lw = round(size * 0.055)
    d.line(pts, fill=INDIGO_HI, width=lw, joint="curve")
    for p in pts[:-1]:
        d.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2],
                  fill=INDIGO_HI)

    ball(d, size * 0.76, size * 0.33, size * 0.135, body=WHITE, ink=DARK)
    d.ellipse([size * 0.76 - size * 0.155, size * 0.33 - size * 0.155,
               size * 0.76 + size * 0.155, size * 0.33 + size * 0.155],
              outline=AMBER, width=round(size * 0.012))
    return img


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, S, S], fill=255)

    for name, fn in (("A_teren", concept_pitch),
                     ("B_minge", concept_ball),
                     ("C_traiectorie", concept_trend)):
        big = fn(S)
        big.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB").save(OUT / f"{name}.png")
        rnd = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        rnd.paste(big, (0, 0), mask)
        rnd.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}_rotund.png")
        print(f"  {name}")

    print(f"\nOptiuni in {OUT}")


if __name__ == "__main__":
    build()
