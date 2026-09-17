"""Validare walk-forward pentru meciurile din cupele europene.

Intrebarea: adauga ceva parametrul de putere a campionatului, sau e la fel de
bine sa tratam toate ligile ca fiind egale?

Comparam trei variante, toate prezicand doar meciuri pe care nu le-au vazut:
  A. fara ajustare  -- fortele echipelor luate ca atare, ca si cum toate
     campionatele ar fi la fel de tari;
  B. cu putere pe campionat -- estimata DOAR din meciuri europene anterioare;
  C. frecventele istorice  -- reper naiv.

Nu exista cote istorice pentru cupele europene, deci reperul "bate piata" nu
poate fi calculat aici. Masuram ce se poate: log-loss si calibrare.
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from data_loader import load_all
from europe_model import (div_la_data, este_european, fit_puteri, incarca_europa,
                          liga_echipei, probabilitati, ratinguri_saptamanale)

PRIMUL_SEZON_TESTAT = 2018
MIN_MECIURI_ANTRENARE = 250


def construieste_tabelul(hist: pd.DataFrame, eu: pd.DataFrame) -> pd.DataFrame:
    """Pentru fiecare meci european: campionatul si fortele fiecarei echipe."""
    apartenenta = liga_echipei(hist)
    eu = eu.copy()
    eu["div_home"] = [div_la_data(apartenenta.get(t), d)
                      for t, d in zip(eu["home_local"], eu["date"])]
    eu["div_away"] = [div_la_data(apartenenta.get(t), d)
                      for t, d in zip(eu["away_local"], eu["date"])]
    eu = eu.dropna(subset=["div_home", "div_away"])

    inainte = len(eu)
    eu = eu[eu["div_home"].map(este_european) & eu["div_away"].map(este_european)]
    if inainte != len(eu):
        print(f"  {inainte - len(eu)} meciuri eliminate: potrivire de nume catre "
              "un campionat din afara Europei")

    # Gruparea pe saptamani reduce de zeci de ori numarul de antrenari.
    eu["moment"] = eu["date"].dt.to_period("W").dt.start_time
    momente = sorted(eu["moment"].unique())
    divs = set(eu["div_home"]) | set(eu["div_away"])
    print(f"  {len(eu):,} meciuri, {len(momente)} saptamani, {len(divs)} campionate implicate")
    print("  antrenez modelele de campionat la fiecare moment...")

    fits = ratinguri_saptamanale(hist, [pd.Timestamp(m) for m in momente], divs)

    randuri = []
    for _, m in eu.iterrows():
        fh = fits.get((pd.Timestamp(m["moment"]), m["div_home"]))
        fa = fits.get((pd.Timestamp(m["moment"]), m["div_away"]))
        if fh is None or fa is None:
            continue
        ih = fh.teams.get(m["home_local"])
        ia = fa.teams.get(m["away_local"])
        if ih is None or ia is None:
            continue
        randuri.append({
            "date": m["date"], "hg": m["hg"], "ag": m["ag"],
            "div_home": m["div_home"], "div_away": m["div_away"],
            "atk_home": fh.attack[ih], "def_home": fh.defence[ih],
            "atk_away": fa.attack[ia], "def_away": fa.defence[ia],
        })
    tabel = pd.DataFrame(randuri)
    print(f"  {len(tabel):,} meciuri cu forte cunoscute pentru ambele echipe")
    return tabel


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1)).mean())


def main() -> int:
    t0 = time.time()
    print("Incarc datele...")
    hist = load_all()
    eu = incarca_europa(hist)
    print(f"  {len(eu):,} meciuri europene cu ambele echipe recunoscute")

    tabel = construieste_tabelul(hist, eu)
    tabel["sezon"] = tabel["date"].dt.year + (tabel["date"].dt.month >= 7).astype(int) - 1
    tabel["rezultat"] = np.where(tabel["hg"] > tabel["ag"], 0,
                                 np.where(tabel["hg"] == tabel["ag"], 1, 2))

    sezoane = sorted(s for s in tabel["sezon"].unique() if s >= PRIMUL_SEZON_TESTAT)
    p_fara, p_cu, y_tot, puteri_finale = [], [], [], None

    print("\nValidare walk-forward pe sezoane:")
    for sezon in sezoane:
        train = tabel[tabel["sezon"] < sezon]
        test = tabel[tabel["sezon"] == sezon]
        if len(train) < MIN_MECIURI_ANTRENARE or test.empty:
            continue

        ligi = sorted(set(train["div_home"]) | set(train["div_away"]))
        puteri, gamma, rho = fit_puteri(train, ligi, pd.Timestamp(f"{sezon}-08-01"))
        puteri_finale = (puteri, gamma, rho)

        for _, m in test.iterrows():
            s_h = puteri.get(m["div_home"], 0.0)
            s_a = puteri.get(m["div_away"], 0.0)
            # A: fara ajustare de campionat
            lam0 = np.exp(m["atk_home"] + m["def_away"] + gamma)
            mu0 = np.exp(m["atk_away"] + m["def_home"])
            p_fara.append(probabilitati(min(lam0, 12), min(mu0, 12), rho))
            # B: cu putere de campionat
            lam1 = np.exp(m["atk_home"] + s_h + m["def_away"] - s_a + gamma)
            mu1 = np.exp(m["atk_away"] + s_a + m["def_home"] - s_h)
            p_cu.append(probabilitati(min(lam1, 12), min(mu1, 12), rho))
            y_tot.append(m["rezultat"])
        print(f"  sezon {sezon}: antrenat pe {len(train):,}, testat pe {len(test)}")

    y = np.array(y_tot)
    A = np.array(p_fara)
    B = np.array(p_cu)
    baza = np.tile(np.bincount(y, minlength=3) / len(y), (len(y), 1))

    print("\n" + "=" * 68)
    print(f"REZULTATE — {len(y):,} meciuri europene prezise fara sa fi fost vazute")
    print("=" * 68)
    print(f"{'':34s} {'log-loss':>10s} {'acuratete':>11s}")
    for nume, p in (("A. fara ajustare de campionat", A),
                    ("B. cu putere de campionat", B),
                    ("C. frecvente istorice", baza)):
        print(f"{nume:34s} {log_loss(p, y):10.5f} {(p.argmax(1) == y).mean():10.2%}")

    castig = log_loss(A, y) - log_loss(B, y)
    print(f"\nCastigul adus de puterea campionatului: {castig:+.5f} log-loss")
    print("(pozitiv = ajuta)")

    if puteri_finale:
        puteri, gamma, rho = puteri_finale
        print(f"\nAvantajul terenului in cupe: {gamma:.3f}   rho: {rho:.3f}")
        print("\nPuterea campionatelor (ultima estimare, mai mare = mai tare):")
        for div, s in sorted(puteri.items(), key=lambda x: -x[1])[:12]:
            print(f"  {div:22s} {s:+.3f}")
        print("  ...")
        for div, s in sorted(puteri.items(), key=lambda x: -x[1])[-4:]:
            print(f"  {div:22s} {s:+.3f}")

    print(f"\nDurata: {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
