"""Cornere si cartonase pentru meciurile afisate.

Se adauga peste predictiile existente, doar la meciurile din cele 12
campionate care au datele astea in arhiva. Feedul suplimentar (Romania si
celelalte 18 tari) nu contine nici cornere, nici cartonase, iar cupele si
nationalele vin de la alta sursa -- acolo sectiunea lipseste pur si simplu.

Ce s-a masurat inainte (backtest_counts.py, 16.676 de meciuri neatinse la
antrenare, castig fata de rata de baza in unitati de log-loss):

  cine da mai multe cornere   +0,037   informativ
  cornere pe echipa           +0,024   informativ
  cartonase pe meci           +0,013   slab informativ
  cartonase pe echipa         +0,010   slab informativ
  cornere pe meci (total)      0,000   NU stie mai mult decat media

Ultima linie e motivul pentru care totalul de cornere apare in aplicatie cu
avertisment, iar niciuna dintre pietele astea nu intra in selectiile automate:
pentru ele nu exista cote istorice cu care sa verificam regula de selectie, iar
ultima data cand am afisat o piata neverificata ("ambele inscriu"), modelul
spunea 80% acolo unde realitatea era 59,8%.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import counts_model

XI = 0.0025             # aceeasi uitare ca in backtest
FEREASTRA_ZILE = 1095
MINIM_MECIURI = 300

LINII = {
    "corners": {"total": [8.5, 9.5, 10.5, 11.5], "echipa": [3.5, 4.5, 5.5]},
    "cards": {"total": [2.5, 3.5, 4.5, 5.5], "echipa": [1.5, 2.5]},
}

# Cat de mult stie modelul, in unitati de log-loss fata de rata de baza.
# Cifrele vin din backtest_counts.py si ajung ca atare in aplicatie.
CALITATE = {
    "corners_total": {"gain": 0.000, "label": "cat media campionatului"},
    "corners_team": {"gain": 0.024, "label": "informativ"},
    "corners_winner": {"gain": 0.037, "label": "cel mai informativ"},
    "cards_total": {"gain": 0.013, "label": "slab informativ"},
    "cards_team": {"gain": 0.010, "label": "slab informativ"},
}


def _coloane(tip: str) -> tuple[str, str]:
    return ("hc", "ac") if tip == "corners" else ("cy", "ca")


def pregateste(hist: pd.DataFrame) -> pd.DataFrame:
    """Adauga coloanele de cartonase totale (galbene + rosii) pe fiecare parte."""
    numeric = {c: pd.to_numeric(hist[c], errors="coerce")
               for c in ("hy", "ay", "hr", "ar")}
    return hist.assign(cy=numeric["hy"] + numeric["hr"],
                       ca=numeric["ay"] + numeric["ar"])


def _fit_liga(liga: pd.DataFrame, coloane: tuple[str, str], azi: pd.Timestamp):
    """Modelul unui campionat plus dispersia totalurilor, ambele doar din trecut."""
    train = liga[(liga["date"] < azi)
                 & (liga["date"] >= azi - pd.Timedelta(days=FEREASTRA_ZILE))]
    train = train.dropna(subset=list(coloane))
    if len(train) < MINIM_MECIURI:
        return None

    echipe = sorted(set(train["home"]) | set(train["away"]))
    idx = {t: k for k, t in enumerate(echipe)}
    varste = (azi - train["date"]).dt.days.to_numpy(dtype=float)
    fit = counts_model.fit_counts(
        train["home"].map(idx).to_numpy(), train["away"].map(idx).to_numpy(),
        train[coloane[0]].to_numpy(dtype=float),
        train[coloane[1]].to_numpy(dtype=float),
        np.exp(-XI * varste), len(echipe), idx)

    medii, observate = [], []
    for r in train.itertuples(index=False):
        rate = fit.rates(r.home, r.away)
        if rate:
            medii.append(sum(rate))
            observate.append(float(getattr(r, coloane[0]))
                             + float(getattr(r, coloane[1])))
    if len(medii) < 200:
        return None
    k = counts_model.fit_dispersie(np.array(medii), np.array(observate))
    return fit, k, len(train)


def _piete(fit, k: float, tip: str, gazda: str, oaspete: str) -> dict | None:
    rate = fit.rates(gazda, oaspete)
    if rate is None:
        return None
    lam, mu = rate

    # Totalul: binomiala negativa, care s-a dovedit mai bine calibrata.
    total_nb = counts_model.nb_pmf(lam + mu, k)
    dist = counts_model.distributii(lam, mu)

    out = {
        "expected": {"home": round(lam, 2), "away": round(mu, 2),
                     "total": round(lam + mu, 2)},
        "total": [{"line": linie,
                   "over": round(counts_model.peste(total_nb, linie), 4),
                   "under": round(1 - counts_model.peste(total_nb, linie), 4)}
                  for linie in LINII[tip]["total"]],
        "home": [{"line": linie,
                  "over": round(counts_model.peste(dist["home"], linie), 4)}
                 for linie in LINII[tip]["echipa"]],
        "away": [{"line": linie,
                  "over": round(counts_model.peste(dist["away"], linie), 4)}
                 for linie in LINII[tip]["echipa"]],
    }
    if tip == "corners":
        out["winner"] = {k2: round(v, 4)
                         for k2, v in counts_model.cine_mai_multe(lam, mu).items()}
    return out


def imbogateste(meciuri: list[dict], hist: pd.DataFrame) -> int:
    """Adauga `extra_markets` la meciurile pentru care avem datele necesare."""
    if not meciuri:
        return 0
    hist = pregateste(hist)
    azi = pd.Timestamp(pd.Timestamp.now().date())

    # Un fit per campionat si tip, refolosit pentru toate meciurile lui.
    cache: dict[tuple[str, str], object] = {}
    imbogatite = 0

    for m in meciuri:
        div = m.get("league")
        if not div or div.startswith(("EU_", "NAT_")):
            continue  # cupe si nationale: alta sursa, fara cornere si cartonase

        extra = {}
        for tip in ("corners", "cards"):
            cheie = (div, tip)
            if cheie not in cache:
                liga = hist[hist["div"] == div]
                cache[cheie] = _fit_liga(liga, _coloane(tip), azi) if not liga.empty else None
            pregatit = cache[cheie]
            if pregatit is None:
                continue
            fit, k, n_train = pregatit
            piete = _piete(fit, k, tip, m["home"], m["away"])
            if piete:
                piete["sample"] = n_train
                extra[tip] = piete

        if extra:
            extra["quality"] = CALITATE
            m["extra_markets"] = extra
            imbogatite += 1

    return imbogatite
