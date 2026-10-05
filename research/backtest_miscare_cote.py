"""Spune ceva miscarea cotelor despre cum se termina selectiile noastre?

Ideea: intre momentul in care casele deschid cotele (cu cateva zile inainte)
si fluierul de start, cotele se misca. Cand o cota scade mult, de obicei au
intrat bani de la pariori informati -- accidentari aflate devreme, echipe de
start, simplu: cineva stie ceva. Intrebarea e daca asta se vede si la
selectiile noastre: cele la care cota a scazut ies mai des decat cele la care
a crescut?

Daca da, se poate folosi in productie: aplicatia vede cotele de patru ori pe
zi, zile la rand inainte de meci, deci stie in ce directie s-au miscat de la
prima observatie pana acum.

Date: football-data publica ambele capete -- cota medie culeasa cu cateva zile
inainte si cota medie de inchidere -- din sezonul 2019/20 incoace.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from backtest_recomandari import LIGI_AFISATE, probabilitati_toate
from data_loader import load_all
from evaluate import SPLIT, devig

# Regula de selectie de acum (recomandari.py).
PRAG_P = 0.60
COTA_MINIMA = 1.45
DEZACORD_SUB, DEZACORD_PESTE = -0.10, 0.05

PIETE = {
    "1": ("open_h", "close_h"), "X": ("open_d", "close_d"),
    "2": ("open_a", "close_a"),
    "over": ("open_o25", "close_o25"), "under": ("open_u25", "close_u25"),
}

NIVELE = [
    ("a scazut peste 5%", 0.05, 9.0),
    ("a scazut 2-5%", 0.02, 0.05),
    ("aproape neschimbata", -0.02, 0.02),
    ("a crescut 2-5%", -0.05, -0.02),
    ("a crescut peste 5%", -9.0, -0.05),
]


def construieste_tabel() -> pd.DataFrame:
    rates = pd.read_csv("out/rates_dual.csv", parse_dates=["date"])
    rates = rates[(rates["date"] >= SPLIT) & rates["div"].isin(LIGI_AFISATE)]

    istoric = load_all()
    coloane = ["div", "date", "home", "away"] + [c for par in PIETE.values() for c in par]
    d = rates.merge(istoric[coloane], on=["div", "date", "home", "away"], how="inner")
    print(f"{len(d):,} meciuri cu predictii, din care cu ambele capete de cota: "
          f"{d[['open_h', 'close_h']].notna().all(axis=1).sum():,}")

    p = probabilitati_toate(d)

    # Probabilitatea pietei, din cotele de inchidere fara marja.
    piata = pd.DataFrame(np.nan, index=d.index, columns=list(PIETE))
    o = d[["close_h", "close_d", "close_a"]].to_numpy(float)
    ok = np.isfinite(o).all(1) & (o > 1).all(1)
    piata.loc[ok, ["1", "X", "2"]] = devig(o[ok])
    ou = d[["close_o25", "close_u25"]].to_numpy(float)
    ok_ou = np.isfinite(ou).all(1) & (ou > 1).all(1)
    piata.loc[ok_ou, ["over", "under"]] = devig(ou[ok_ou])

    castigat = {
        "1": d["result"] == 0, "X": d["result"] == 1, "2": d["result"] == 2,
        "over": d["over25"] == 1, "under": d["over25"] == 0,
    }

    bucati = []
    for nume, (deschidere, inchidere) in PIETE.items():
        bucati.append(pd.DataFrame({
            "piata": nume,
            "p": p[nume].to_numpy(),
            "p_piata": piata[nume].to_numpy(),
            "cota_deschidere": d[deschidere].to_numpy(float),
            "cota_inchidere": d[inchidere].to_numpy(float),
            "castigat": castigat[nume].to_numpy(),
        }))
    t = pd.concat(bucati, ignore_index=True).dropna()
    t = t[(t["cota_deschidere"] > 1) & (t["cota_inchidere"] > 1)]
    # Pozitiv = cota a scazut (au intrat bani pe rezultatul asta).
    t["miscare"] = t["cota_deschidere"] / t["cota_inchidere"] - 1
    t["dezacord"] = t["p"] - t["p_piata"]
    return t


def raport(eticheta: str, sel: pd.DataFrame) -> None:
    if len(sel) < 30:
        print(f"  {eticheta:<24} {len(sel):>6} selectii (prea putine)")
        return
    rata = sel["castigat"].mean()
    profit_inchidere = np.where(sel["castigat"], sel["cota_inchidere"] - 1, -1.0)
    profit_deschidere = np.where(sel["castigat"], sel["cota_deschidere"] - 1, -1.0)
    se = profit_inchidere.std(ddof=1) / np.sqrt(len(sel))
    print(f"  {eticheta:<24} {len(sel):>6} selectii  {rata:6.1%} reusite  "
          f"ROI la inchidere {profit_inchidere.mean():+6.2%} "
          f"(t={profit_inchidere.mean() / se:+5.2f})  "
          f"la deschidere {profit_deschidere.mean():+6.2%}")


def main() -> int:
    t = construieste_tabel()
    regula = t[(t["p"] >= PRAG_P) & (t["cota_inchidere"] >= COTA_MINIMA)
               & (t["dezacord"] >= DEZACORD_SUB) & (t["dezacord"] <= DEZACORD_PESTE)]

    print(f"\nSelectiile regulii de acum ({len(regula):,}), dupa cum s-a miscat cota:")
    for eticheta, jos, sus in NIVELE:
        raport(eticheta, regula[(regula["miscare"] > jos) & (regula["miscare"] <= sus)])
    raport("toate", regula)

    # Pentru comparatie: acelasi lucru pe toate rezultatele posibile, nu doar
    # pe selectiile noastre. Arata daca efectul e al pietei sau al regulii.
    print(f"\nToate pietele, fara regula ({len(t):,}):")
    for eticheta, jos, sus in NIVELE:
        raport(eticheta, t[(t["miscare"] > jos) & (t["miscare"] <= sus)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
