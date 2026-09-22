"""Modelul pentru meciuri intre echipe nationale.

Acelasi Dixon-Coles ca la cluburi, dar pe un bazin separat: nationalele nu
apar nicaieri in datele de club, iar fortele lor nu se pot deduce din ele.

Doua lucruri difera fata de campionate si conteaza:

1. Meciurile sunt rare. O nationala joaca ~10 pe an, fata de ~38 un club, deci
   uitarea trebuie sa fie mult mai lenta -- altfel n-ar mai ramane nimic in
   fereastra de antrenare.
2. Bazinul e imens si prost conectat: Vanuatu nu joaca niciodata cu Islanda.
   Legaturile exista prin preliminarii intercontinentale si amicale, dar sunt
   subtiri, deci pentru echipele exotice increderea trebuie sa fie mica.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from dixon_coles import fit_dixon_coles, markets_from_rates

# Ales in backtest_national.py: vezi comentariul de acolo pentru cifre.
XI_NATIONAL = 0.0008

# Sub atatea meciuri in fereastra, fortele unei echipe sunt zgomot curat.
MINIM_MECIURI = 6


def fit(hist: pd.DataFrame, azi: pd.Timestamp, xi: float = XI_NATIONAL):
    """Antreneaza pe tot ce s-a jucat inainte de `azi`."""
    train = hist[hist["date"] < azi]
    if len(train) < 300:
        return None
    echipe = sorted(set(train["home"]) | set(train["away"]))
    idx = {t: k for k, t in enumerate(echipe)}
    varste = (azi - train["date"]).dt.days.to_numpy(dtype=float)
    return fit_dixon_coles(
        train["home"].map(idx).to_numpy(),
        train["away"].map(idx).to_numpy(),
        train["hg"].to_numpy().astype(int),
        train["ag"].to_numpy().astype(int),
        np.exp(-xi * varste),
        len(echipe), idx,
    )


def meciuri_jucate(hist: pd.DataFrame, echipa: str, azi: pd.Timestamp,
                   zile: int = 1460) -> int:
    """Cate meciuri are echipa in fereastra recenta: masura increderii."""
    recent = hist[(hist["date"] < azi) & (hist["date"] >= azi - pd.Timedelta(days=zile))]
    return int(((recent["home"] == echipa) | (recent["away"] == echipa)).sum())


def probabilitati(model, gazda: str, oaspete: str) -> dict | None:
    """Probabilitatile pe piete, sau None daca una dintre echipe e necunoscuta.

    Nu inventam o echipa medie: o nationala nevazuta niciodata inseamna ca nu
    stim nimic despre ea, iar un procent scos din media bazinului ar fi mai
    inselator decat lipsa lui.
    """
    if model is None:
        return None
    ih, ia = model.teams.get(gazda), model.teams.get(oaspete)
    if ih is None or ia is None:
        return None

    lam = float(np.exp(model.attack[ih] + model.defence[ia] + model.home_adv))
    mu = float(np.exp(model.attack[ia] + model.defence[ih]))
    lam, mu = min(lam, 8.0), min(mu, 8.0)

    p = markets_from_rates(lam, mu, model.rho)
    p["p_under25"] = 1 - p["p_over25"]
    p["p_no_btts"] = 1 - p["p_btts"]
    return {"probs": p, "lam": lam, "mu": mu}
