"""Cornere si cartonase pentru meciurile de nationale. NEFOLOSIT DEOCAMDATA.

Scris ca sa acopere pauzele competitionale, cand aplicatia arata numai
nationale si sectiunea de cornere lipsea de peste tot. Masurat insa in
`backtest_counts_national.py`, pe 409 meciuri de verificare, s-a dovedit mai
slab decat simpla medie la TOATE pietele: intre -0,01 si -0,50 la log-loss.

Cauza e limpede: o nationala are vreo 12 meciuri in bazin, iar din 12
observatii nu ies doua forte (produs si concedat) -- iese zgomot imbracat in
procente. Franarea catre medie (`ridge`) reduce paguba, dar tot nu o intoarce.

Deci modulul nu se leaga la `predict.py`. Ramane aici pentru cand bazinul va fi
de doua-trei ori mai mare; atunci se reia masuratoarea, si daca trece pragul,
se leaga. Colectarea continua intre timp.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import counts_model
from fetch_national_stats import incarca
from predict_counts import LINII

XI = 0.0006          # nationalele joaca rar: uitare lenta, ca la rezultate
MINIM_MECIURI = 400  # sub atat, fortele pe echipa sunt zgomot
MINIM_PER_ECHIPA = 8


def _pregateste(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(cy=df["hy"].astype(float) + df["hr"].astype(float),
                     ca=df["ay"].astype(float) + df["ar"].astype(float))


def _fit(df: pd.DataFrame, coloane: tuple[str, str], azi: pd.Timestamp):
    train = df[df["date"] < azi].dropna(subset=list(coloane))
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

    aparitii = pd.concat([train["home"], train["away"]]).value_counts().to_dict()
    return fit, k, len(train), aparitii


def _piete(pregatit, tip: str, gazda: str, oaspete: str) -> dict | None:
    fit, k, n_train, aparitii = pregatit
    # O nationala cu doua meciuri in bazin n-are forte, are zgomot.
    if min(aparitii.get(gazda, 0), aparitii.get(oaspete, 0)) < MINIM_PER_ECHIPA:
        return None

    rate = fit.rates(gazda, oaspete)
    if rate is None:
        return None
    lam, mu = rate
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
        "sample": n_train,
    }
    if tip == "corners":
        out["winner"] = {k2: round(v, 4)
                         for k2, v in counts_model.cine_mai_multe(lam, mu).items()}
    return out


def imbogateste(meciuri: list[dict]) -> int:
    """Adauga `extra_markets` la meciurile de nationale, unde se poate."""
    nationale = [m for m in meciuri if str(m.get("league", "")).startswith("NAT_")]
    if not nationale:
        return 0

    df = incarca(doar_utile=True)
    if df.empty:
        print("  (inca nu sunt statistici adunate pentru nationale)")
        return 0
    df = _pregateste(df)
    azi = pd.Timestamp(pd.Timestamp.now().date())

    pregatite = {tip: _fit(df, coloane, azi) for tip, coloane in
                 (("corners", ("hc", "ac")), ("cards", ("cy", "ca")))}
    if not any(pregatite.values()):
        print(f"  (prea putine statistici de nationale: {len(df)} meciuri)")
        return 0

    imbogatite = 0
    for m in nationale:
        extra = {}
        for tip, pregatit in pregatite.items():
            if pregatit is None:
                continue
            piete = _piete(pregatit, tip, m["home"], m["away"])
            if piete:
                extra[tip] = piete
        if extra:
            m["extra_markets"] = extra
            imbogatite += 1
    return imbogatite
