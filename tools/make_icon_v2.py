"""Concepte noi de iconita, pentru ales inainte de a schimba ceva.

Fiecare concept e un desen pe stratul de sus, peste un fundal. Totul se
deseneaza la 4x si se micsoreaza la final, ca marginile sa iasa netede.

Zona sigura: flutter_launcher_icons adauga un inset de 16%, apoi launcherul
taie un cerc. Ce e important trebuie sa stea in cercul de raza ~0.45 din
latura desenului, altfel se taie pe telefoanele cu iconite rotunde.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
SS = 4
S = SIZE * SS

ALB = (245, 247, 252)
CHIHLIMBAR = (251, 191, 36)
INDIGO_HI = (79, 70, 229)
INDIGO_LO = (49, 46, 129)
INDIGO_ADANC = (30, 27, 75)
GLOW = (129, 140, 248)

FONT = "C:/Windows/Fonts/segoeuib.ttf"


def degrade(size: int, sus: tuple, jos: tuple, lumina: tuple | None = GLOW) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        e = (y / (size - 1)) ** 1.2
        rand = tuple(round(sus[i] + (jos[i] - sus[i]) * e) for i in range(3))
        for x in range(size):
            px[x, y] = rand
    if lumina:
        masca = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(masca)
        cx, cy, r = size * 0.26, size * 0.20, size * 0.66
        for i in range(90):
            k = 1 - i / 90
            rr = r * k
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=int(22 * (1 - k)))
        img.paste(Image.new("RGB", (size, size), lumina), (0, 0), masca)
    return img


# --- Conceptele ---------------------------------------------------------------

def _scut(cx: float, sus: float, jos: float, lat: float) -> list[tuple[float, float]]:
    """Conturul unui scut simetric: umeri drepti, laturi, apoi o curba spre varf."""
    umar = sus + (jos - sus) * 0.10
    mijloc = sus + (jos - sus) * 0.50
    dreapta = [(cx, sus), (cx + lat * 0.55, sus + (umar - sus) * 0.35),
               (cx + lat, umar), (cx + lat, mijloc)]
    for i in range(1, 25):
        t = i / 24
        # Curba de la latura spre varf, ca un sfert de elipsa usor ascutit.
        x = cx + lat * math.cos(t * math.pi / 2) ** 1.15
        y = mijloc + (jos - mijloc) * math.sin(t * math.pi / 2)
        dreapta.append((x, y))
    stanga = [(2 * cx - x, y) for x, y in reversed(dreapta[:-1])]
    return dreapta + stanga


def scut_cu_grafic(d: ImageDraw.ImageDraw, s: int) -> None:
    """Un scut de club, cu un grafic care urca si un punct galben in varf."""
    contur = _scut(s * 0.5, s * 0.10, s * 0.90, s * 0.36)
    d.polygon(contur, fill=(55, 50, 150))
    d.line(contur + [contur[0], contur[1]], fill=ALB, width=round(s * 0.032),
           joint="curve")

    puncte = [(s * 0.30, s * 0.64), (s * 0.43, s * 0.50),
              (s * 0.55, s * 0.57), (s * 0.70, s * 0.36)]
    d.line(puncte, fill=ALB, width=round(s * 0.040), joint="curve")
    for x, y in puncte[:-1]:
        r = s * 0.028
        d.ellipse([x - r, y - r, x + r, y + r], fill=ALB)
    x, y = puncte[-1]
    r = s * 0.062
    d.ellipse([x - r, y - r, x + r, y + r], fill=CHIHLIMBAR)


def poarta_cu_procent(d: ImageDraw.ImageDraw, s: int) -> None:
    """Poarta vazuta din fata, cu plasa, si un procent mare in fata ei."""
    lw = round(s * 0.040)
    st, dr, sus, jos = s * 0.10, s * 0.90, s * 0.22, s * 0.76
    # Plasa rara: deasa, la dimensiunea de pe ecran devenea o pata.
    plasa = round(s * 0.010)
    for i in range(1, 5):
        x = st + (dr - st) * i / 5
        d.line([(x, sus), (x, jos)], fill=(140, 145, 220), width=plasa)
    for i in range(1, 3):
        y = sus + (jos - sus) * i / 3
        d.line([(st, y), (dr, y)], fill=(140, 145, 220), width=plasa)
    d.line([(st, jos + lw / 2), (st, sus), (dr, sus), (dr, jos + lw / 2)],
           fill=ALB, width=lw, joint="curve")

    font = ImageFont.truetype(FONT, round(s * 0.50))
    text = "%"
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    w, h = r - l, b - t
    x, y = s * 0.5 - w / 2 - l, s * 0.50 - h / 2 - t + s * 0.02
    # Un contur inchis in jurul procentului, ca sa se desprinda de plasa.
    d.text((x, y), text, font=font, fill=CHIHLIMBAR,
           stroke_width=round(s * 0.024), stroke_fill=INDIGO_ADANC)


def bilet(d: ImageDraw.ImageDraw, s: int, culoare=INDIGO_ADANC, accent=ALB) -> None:
    """Un bilet de pariu, usor inclinat, cu o bifa."""
    strat = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ds = ImageDraw.Draw(strat)
    st, dr, sus, jos = s * 0.15, s * 0.85, s * 0.20, s * 0.80
    ds.rounded_rectangle([st, sus, dr, jos], radius=s * 0.06, fill=culoare)
    # Crestaturile laterale, ca la un bilet adevarat.
    r = s * 0.055
    ym = s * 0.42
    for x in (st, dr):
        ds.ellipse([x - r, ym - r, x + r, ym + r], fill=(0, 0, 0, 0))
    # Linia punctata de rupere.
    for i in range(11):
        x0 = st + s * 0.08 + i * (dr - st - s * 0.16) / 11
        ds.line([(x0, ym), (x0 + s * 0.026, ym)], fill=accent, width=round(s * 0.012))
    # Randuri de text, schitate.
    for i, lung in enumerate((0.42, 0.30)):
        y = sus + s * 0.07 + i * s * 0.065
        ds.rounded_rectangle([st + s * 0.08, y, st + s * (0.08 + lung), y + s * 0.028],
                             radius=s * 0.014, fill=accent)
    # Bifa.
    ds.line([(s * 0.37, s * 0.60), (s * 0.46, s * 0.69), (s * 0.65, s * 0.50)],
            fill=accent, width=round(s * 0.052), joint="curve")
    strat = strat.rotate(-12, resample=Image.BICUBIC, center=(s / 2, s / 2))
    d._image.alpha_composite(strat)


def _pentagon(cx: float, cy: float, r: float, rot: float) -> list[tuple[float, float]]:
    return [(cx + r * math.cos(math.radians(rot + 72 * k)),
             cy + r * math.sin(math.radians(rot + 72 * k))) for k in range(5)]


def _minge(baza: Image.Image, cx: float, cy: float, r: float) -> None:
    """O minge clasica: pentagon in centru si cinci pe margine, taiate de cerc."""
    s = baza.size[0]
    strat = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(strat)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ALB)
    rp = r * 0.36
    d.polygon(_pentagon(cx, cy, rp, -90), fill=INDIGO_ADANC)
    for k in range(5):
        ung = math.radians(-90 + 72 * k)
        px, py = cx + r * 0.98 * math.cos(ung), cy + r * 0.98 * math.sin(ung)
        d.polygon(_pentagon(px, py, rp * 0.95, -90 + 72 * k + 36), fill=INDIGO_ADANC)
        # Cusaturile dintre pentagonul central si cele de pe margine.
        vx, vy = (cx + rp * math.cos(ung), cy + rp * math.sin(ung))
        d.line([(vx, vy), (cx + r * 0.66 * math.cos(ung), cy + r * 0.66 * math.sin(ung))],
               fill=INDIGO_ADANC, width=round(r * 0.07))
    masca = Image.new("L", (s, s), 0)
    ImageDraw.Draw(masca).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    taiat = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    taiat.paste(strat, (0, 0), masca)
    # Un inel subtire, ca mingea sa se desprinda de fundal.
    ImageDraw.Draw(taiat).ellipse([cx - r, cy - r, cx + r, cy + r],
                                  outline=INDIGO_ADANC, width=round(r * 0.05))
    baza.alpha_composite(taiat)


def bare_si_minge(d: ImageDraw.ImageDraw, s: int) -> None:
    """Trei bare care urca, iar deasupra celei mai inalte, o minge."""
    latime = s * 0.17
    spatiu = s * 0.055
    baza = s * 0.86
    inaltimi = (0.24, 0.38, 0.50)
    st = s * 0.5 - (3 * latime + 2 * spatiu) / 2
    for i, h in enumerate(inaltimi):
        x0 = st + i * (latime + spatiu)
        culoare = ALB if i < 2 else CHIHLIMBAR
        d.rounded_rectangle([x0, baza - s * h, x0 + latime, baza],
                            radius=s * 0.035, fill=culoare)
    # Mingea sta pe bara cea mai inalta, ca punctul pe i.
    x_ultima = st + 2 * (latime + spatiu) + latime / 2
    r = s * 0.115
    _minge(d._image, x_ultima, baza - s * 0.50 - r - s * 0.03, r)


CONCEPTE = {
    "A": ("Scut cu grafic", scut_cu_grafic, (INDIGO_HI, INDIGO_LO)),
    "B": ("Poartă și procent", poarta_cu_procent, (INDIGO_HI, INDIGO_LO)),
    "C": ("Biletul", bilet, ((253, 211, 77), (245, 158, 11))),
    # Acelasi bilet, cu culorile inversate: pe indigo, ca restul aplicatiei.
    "D": ("Biletul, pe indigo",
          lambda d, s: bilet(d, s, culoare=CHIHLIMBAR, accent=INDIGO_ADANC),
          (INDIGO_HI, INDIGO_LO)),
    "E": ("Bare și minge", bare_si_minge, (INDIGO_HI, INDIGO_LO)),
}


def straturi(cheie: str) -> tuple[Image.Image, Image.Image]:
    """Fundalul si desenul, la rezolutia mare."""
    _, deseneaza, (sus, jos) = CONCEPTE[cheie]
    lumina = GLOW if sus[2] > 150 else (255, 245, 200)
    fundal = degrade(S, sus, jos, lumina).convert("RGBA")
    desen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    deseneaza(ImageDraw.Draw(desen), S)
    return fundal, desen


def rotund(cheie: str, latura: int) -> Image.Image:
    """Cum arata pe un telefon cu iconite rotunde (inset 16%, masca cerc)."""
    fundal, desen = straturi(cheie)
    lat = round(S * 0.68)
    fundal.alpha_composite(desen.resize((lat, lat), Image.LANCZOS),
                           ((S - lat) // 2, (S - lat) // 2))
    masca = Image.new("L", (S, S), 0)
    ImageDraw.Draw(masca).ellipse([0, 0, S, S], fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(fundal, (0, 0), masca)
    return out.resize((latura, latura), Image.LANCZOS)


def planșa(dest: Path) -> None:
    """Toate conceptele una langa alta: mare, si cat pe ecranul telefonului."""
    mare, mic = 300, 72
    pad = 40
    lat = len(CONCEPTE) * (mare + pad) + pad
    inalt = mare + mic + 170
    img = Image.new("RGB", (lat, inalt), (11, 15, 26))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 26)
    font_mic = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
    for i, cheie in enumerate(CONCEPTE):
        x = pad + i * (mare + pad)
        img.paste(rotund(cheie, mare), (x, pad), rotund(cheie, mare))
        mica = rotund(cheie, mic)
        img.paste(mica, (x + (mare - mic) // 2, pad + mare + 24), mica)
        eticheta = f"{cheie}. {CONCEPTE[cheie][0]}"
        l, _, r, _ = d.textbbox((0, 0), eticheta, font=font)
        d.text((x + (mare - (r - l)) / 2, pad + mare + mic + 40), eticheta,
               font=font, fill=(226, 232, 240))
        nota = "cât pe ecran"
        l, _, r, _ = d.textbbox((0, 0), nota, font=font_mic)
        d.text((x + (mare - (r - l)) / 2, pad + mare + mic + 80), nota,
               font=font_mic, fill=(148, 163, 184))
    img.save(dest)


def scrie(cheie: str, dest_dir: Path) -> None:
    """Fisierele pentru flutter_launcher_icons, din conceptul ales."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    fundal, desen = straturi(cheie)
    complet = fundal.copy()
    complet.alpha_composite(desen)
    complet.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB").save(dest_dir / "icon.png")
    fundal.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB").save(dest_dir / "background.png")
    desen.resize((SIZE, SIZE), Image.LANCZOS).save(dest_dir / "foreground.png")
    rotund(cheie, SIZE).save(dest_dir / "preview_round.png")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "scrie":
        scrie(sys.argv[2], Path(__file__).parent.parent / "app" / "assets" / "icon")
        print(f"Iconita {sys.argv[2]} scrisa.")
    else:
        dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("planse_iconite.png")
        planșa(dest)
        print(f"Plansa: {dest}")
