"""Ce fel de selectie automata se confirma istoric, si ce fel nu.

Aplicatia va avea o sectiune care alege singura cateva meciuri. Intrebarea nu e
"ce alegem", ci "ce alegere rezista la verificare". Testam pe cele ~97.000 de
predictii walk-forward trei reguli, toate pe aceleasi meciuri:

  1. dupa AVANTAJ fata de cota  -- adica exact ce a iesit pe minus in backtest;
  2. dupa INCREDEREA modelului  -- probabilitatea cea mai mare, indiferent de cota;
  3. increderea modelului, dar DOAR unde piata e de acord cu el.

A treia porneste de la o observatie din propriul nostru backtest: cu cat modelul
se indeparteaza mai mult de cota, cu atat greseste mai des. Deci dezacordul mare
nu e semn de valoare, ci de eroare.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from dixon_coles import markets_from_rates
from evaluate import SPLIT, devig

ALPHA = 0.50
# Doar competitiile care vor aparea in aplicatie.
LIGI_AFISATE = {"E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1", "ROU_Superliga"}


def probabilitati_toate(d: pd.DataFrame) -> pd.DataFrame:
    """Probabilitatile pentru fiecare piata, din ratele salvate de backtest."""
    lam = np.exp(ALPHA * np.log(d["lam_g"]) + (1 - ALPHA) * np.log(d["lam_s"]))
    mu = np.exp(ALPHA * np.log(d["mu_g"]) + (1 - ALPHA) * np.log(d["mu_s"]))
    randuri = []
    for l, m, r in zip(lam, mu, d["rho"]):
        p = markets_from_rates(float(l), float(m), float(r))
        randuri.append([p["p_home"], p["p_draw"], p["p_away"],
                        p["p_over25"], 1 - p["p_over25"],
                        p["p_btts"], 1 - p["p_btts"]])
    return pd.DataFrame(randuri, columns=["1", "X", "2", "over", "under", "btts", "nobtts"],
                        index=d.index)


def construieste(d: pd.DataFrame) -> pd.DataFrame:
    """Un rand per (meci, piata), cu probabilitate, cota si rezultat."""
    p = probabilitati_toate(d)
    castigat = pd.DataFrame({
        "1": d["result"] == 0, "X": d["result"] == 1, "2": d["result"] == 2,
        "over": d["over25"] == 1, "under": d["over25"] == 0,
        "btts": d["btts"] == 1, "nobtts": d["btts"] == 0,
    }, index=d.index)
    cote = pd.DataFrame({
        "1": d["max_h"], "X": d["max_d"], "2": d["max_a"],
        "over": d["max_o25"], "under": d["max_u25"],
        "btts": np.nan, "nobtts": np.nan,
    }, index=d.index)

    # Probabilitatea implicita a pietei, pentru masurarea dezacordului.
    o = d[["psc_h", "psc_d", "psc_a"]].to_numpy(float)
    o = np.where(np.isnan(o), d[["avg_h", "avg_d", "avg_a"]].to_numpy(float), o)
    ok = np.isfinite(o).all(1) & (o > 1).all(1)
    piata = pd.DataFrame(np.nan, index=d.index, columns=["1", "X", "2", "over", "under",
                                                        "btts", "nobtts"])
    piata.loc[ok, ["1", "X", "2"]] = devig(o[ok])
    ou = d[["max_o25", "max_u25"]].to_numpy(float)
    ok_ou = np.isfinite(ou).all(1) & (ou > 1).all(1)
    piata.loc[ok_ou, ["over", "under"]] = devig(ou[ok_ou])

    bucati = []
    for piata_nume in p.columns:
        bucati.append(pd.DataFrame({
            "div": d["div"].to_numpy(), "date": d["date"].to_numpy(),
            "piata": piata_nume,
            "p": p[piata_nume].to_numpy(),
            "cota": cote[piata_nume].to_numpy(),
            "p_piata": piata[piata_nume].to_numpy(),
            "castigat": castigat[piata_nume].to_numpy(),
        }))
    return pd.concat(bucati, ignore_index=True)


def raport(nume: str, sel: pd.DataFrame, total_meciuri: int) -> None:
    if sel.empty:
        print(f"  {nume:46s} nicio selectie")
        return
    rata = sel["castigat"].mean()
    cu_cota = sel.dropna(subset=["cota"])
    cu_cota = cu_cota[cu_cota["cota"] > 1]
    if len(cu_cota):
        profit = np.where(cu_cota["castigat"], cu_cota["cota"] - 1, -1.0)
        roi = profit.mean()
        se = profit.std(ddof=1) / np.sqrt(len(profit))
        t = roi / se if se > 0 else 0
        roi_txt = f"{roi:+6.2%} (t={t:+5.2f})"
    else:
        roi_txt = "     fara cote"
    pe_zi = len(sel) / max(total_meciuri, 1)
    print(f"  {nume:46s} {len(sel):6,} sel. {rata:6.1%} reusite  ROI {roi_txt}  "
          f"{pe_zi:.2f}/meci")


def main() -> int:
    d = pd.read_csv("out/rates_dual.csv", parse_dates=["date"])
    d = d[(d["date"] >= SPLIT) & (d["div"].isin(LIGI_AFISATE))].reset_index(drop=True)
    print(f"Test pe {len(d):,} meciuri din ligile afisate, 2019-2026\n")

    t = construieste(d)
    t["dezacord"] = t["p"] - t["p_piata"]
    t["avantaj"] = t["p"] * t["cota"] - 1

    print("REGULA 1 — dupa avantajul fata de cota (ce am masurat deja ca pierde):")
    for prag in (0.05, 0.10):
        raport(f"avantaj > {prag:.0%}", t[t["avantaj"] > prag], len(d))

    print("\nREGULA 2 — dupa increderea modelului, indiferent de cota:")
    for prag in (0.55, 0.60, 0.65, 0.70, 0.75):
        raport(f"probabilitate >= {prag:.0%}", t[t["p"] >= prag], len(d))

    print("\nREGULA 3 — increderea modelului, dar numai unde piata e de acord:")
    for prag in (0.60, 0.65, 0.70):
        for tol in (0.05, 0.08):
            sel = t[(t["p"] >= prag) & (t["dezacord"].abs() <= tol)]
            raport(f"probabilitate >= {prag:.0%} si dezacord <= {tol:.0%}", sel, len(d))

    print("\nPentru comparatie, cat de des se confirma fiecare piata in general:")
    for piata_nume in ("1", "X", "2", "over", "under", "btts", "nobtts"):
        sub = t[t["piata"] == piata_nume]
        print(f"  {piata_nume:8s} {sub['castigat'].mean():5.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
