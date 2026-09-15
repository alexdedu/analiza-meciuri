"""Genereaza iconita aplicatiei: terenul de fotbal vazut de sus.

Geometrie pura, fara minge si fara text: contur, linie de mijloc, cerc central
si cele doua careuri, pe un degrade indigo. La 48 de pixeli liniile raman
lizibile, ceea ce nu e cazul pentru desene mai incarcate.

Randam la 4x si micsoram la final, ca marginile sa iasa netede.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent.parent / "app" / "assets" / "icon"
SIZE = 1024
SS = 4  # supersampling
S = SIZE * SS

INDIGO_HI = (79, 70, 229)
INDIGO_LO = (49, 46, 129)
GLOW = (129, 140, 248)
LINES = (245, 247, 252)

# Geometria terenului, ca fractiuni din latura. Coltul cel mai departat de centru
# ajunge la 0.483 din latura -- exact cat incape in zona vizibila a unei iconite
# adaptive dupa insetul de 16% (0.483 x 0.68 = 0.329, iar zona sigura are raza
# 0.33). Daca maresti dreptunghiul, colturile terenului vor fi taiate pe
# telefoanele cu iconite rotunde.
LEFT, RIGHT = 0.19, 0.81
TOP, BOTTOM = 0.13, 0.87


def gradient_background(size: int) -> Image.Image:
    """Degrade vertical indigo, cu o usoara lumina in coltul din stanga-sus."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        e = (y / (size - 1)) ** 1.2
        row = tuple(round(INDIGO_HI[i] + (INDIGO_LO[i] - INDIGO_HI[i]) * e) for i in range(3))
        for x in range(size):
            px[x, y] = row

    glow = Image.new("L", (size, size), 0)
    gd = ImageDraw.Draw(glow)
    cx, cy, r = size * 0.26, size * 0.20, size * 0.66
    steps = 90
    for i in range(steps):
        k = 1 - i / steps
        rr = r * k
        gd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=int(22 * (1 - k)))
    img.paste(Image.new("RGB", (size, size), GLOW), (0, 0), glow)
    return img


def draw_pitch(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Liniile terenului."""
    lw = round(size * 0.020)
    left, right = size * LEFT, size * RIGHT
    top, bottom = size * TOP, size * BOTTOM
    mid_x, mid_y = size * 0.5, size * 0.5

    draw.rounded_rectangle([left, top, right, bottom], radius=size * 0.02,
                           outline=LINES, width=lw)
    draw.line([(left, mid_y), (right, mid_y)], fill=LINES, width=lw)

    r_circle = size * 0.115
    draw.ellipse([mid_x - r_circle, mid_y - r_circle, mid_x + r_circle, mid_y + r_circle],
                 outline=LINES, width=lw)
    r_spot = size * 0.017
    draw.ellipse([mid_x - r_spot, mid_y - r_spot, mid_x + r_spot, mid_y + r_spot],
                 fill=LINES)

    box_w, box_h = size * 0.34, size * 0.105
    for y0, y1 in ((top, top + box_h), (bottom - box_h, bottom)):
        draw.rectangle([mid_x - box_w / 2, y0, mid_x + box_w / 2, y1],
                       outline=LINES, width=lw)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Iconita completa (fundal + teren), pentru launcherele vechi.
    full = gradient_background(S).convert("RGBA")
    draw_pitch(ImageDraw.Draw(full), S)
    full.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB").save(OUT / "icon.png")

    # 2. Doar fundalul, ca strat de jos al iconitei adaptive.
    gradient_background(S).resize((SIZE, SIZE), Image.LANCZOS).save(OUT / "background.png")

    # 3. Doar liniile, ca strat de sus. Le lasam la dimensiunea intreaga: insetul
    #    de 16% adaugat de flutter_launcher_icons le aduce fix in zona sigura.
    #    Orice micsorare suplimentara aici ar face terenul prea mic.
    fg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_pitch(ImageDraw.Draw(fg), S)
    fg.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / "foreground.png")

    # 4. Previzualizare: cum arata pe un telefon cu iconite rotunde.
    preview = gradient_background(S).convert("RGBA")
    inset = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_pitch(ImageDraw.Draw(inset), S)
    side = round(S * 0.68)
    offset = (S - side) // 2
    preview.alpha_composite(inset.resize((side, side), Image.LANCZOS), (offset, offset))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, S, S], fill=255)
    round_icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    round_icon.paste(preview, (0, 0), mask)
    round_icon.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / "preview_round.png")

    for name in ("icon.png", "background.png", "foreground.png", "preview_round.png"):
        print(f"  {name:18s} {(OUT / name).stat().st_size // 1024:4d} KB")


if __name__ == "__main__":
    build()
    print(f"\nIconite generate in {OUT}")
