"""Cartonasele din prima repriza: se pot prezice mai bine decat media?

Doua cai, comparate pe aceleasi meciuri:

A. Model direct pe datele de repriza: fiecare echipa cu cat ia si cat provoaca
   in primele 45 de minute. Curat, dar invata din putine date -- trei sezoane
   adunate din API, nu zece ca la meciul intreg.

B. Modelul de meci intreg, care stie echipele din zece ani de date, inmultit cu
   partea din cartonase care se da de obicei in prima repriza (~33%) si cu
   factorul arbitrului. Foloseste mai multe date, dar presupune ca partea din
   prima repriza e aceeasi pentru toata lumea.

Masuram pe liniile obisnuite: peste 0.5, 1.5 si 2.5 cartonase in prima repriza,
plus "gazda primeste cartonas in prima repriza". Totul invatat doar din trecut.

REZULTAT (6 oct 2026, 3.712 meciuri de verificare): NU SE POATE.
  - A (direct) e mai slab decat media pe toate liniile: din trei sezoane de
    date pe repriza, fortele pe echipa ies zgomot.
  - B (meci intreg x parte x arbitru) bate media, dar cu castiguri de
    0,0015-0,0027 si t intre 0,55 si 1,14 -- adica nimic deosebit de zgomot.
Prima repriza are prea putine cartonase (in medie 1,3) ca diferentele dintre
echipe sa se vada peste intamplare. Nu intra in aplicatie.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import counts_model
from data_loader import load_all
from fetch_card_events import incarca as incarca_reprize
from fetch_referees import incarca as incarca_arbitri

XI = 0.0025
FEREASTRA_ZILE = 1095
PAS_ZILE = 14
MINIM_REPRIZA = 250       # meciuri cu date de repriza in fereastra
MINIM_INTREG = 300
K_ARBITRU = 120.0

LINII = [0.5, 1.5, 2.5]


def pregateste() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Meciurile cu repriza (A, B) si istoricul complet de meci intreg (B)."""
    reprize = incarca_reprize(doar_utile=True)
    reprize = reprize.dropna(subset=["home", "away"])
    reprize = reprize[(reprize["home"] != "") & (reprize["away"] != "")]
    reprize = reprize.assign(
        c1=reprize["hy1"] + reprize["hr1"], a1=reprize["ay1"] + reprize["ar1"],
        c_tot=(reprize["hy1"] + reprize["hy2"] + reprize["hr1"] + reprize["hr2"]),
        a_tot=(reprize["ay1"] + reprize["ay2"] + reprize["ar1"] + reprize["ar2"]))
    reprize["date"] = pd.to_datetime(reprize["date"]).dt.normalize()

    arbitri = incarca_arbitri()
    if not arbitri.empty:
        arbitri = arbitri[(arbitri["referee"] != "") & (arbitri["home"] != "")]
        arbitri["date"] = arbitri["date"].dt.normalize()
        reprize = reprize.merge(arbitri[["div", "date", "home", "away", "referee"]],
                                on=["div", "date", "home", "away"], how="left")
    reprize["referee"] = reprize.get("referee", pd.Series(dtype=str)).fillna("")

    intreg = load_all()
    numeric = {c: pd.to_numeric(intreg[c], errors="coerce") for c in ("hy", "ay", "hr", "ar")}
    intreg = intreg.assign(cy=numeric["hy"] + numeric["hr"],
                           ca=numeric["ay"] + numeric["ar"]).dropna(subset=["cy", "ca"])
    if not arbitri.empty:
        intreg = intreg.merge(arbitri[["div", "date", "home", "away", "referee"]],
                              on=["div", "date", "home", "away"], how="left")
    intreg["referee"] = intreg.get("referee", pd.Series(dtype=str)).fillna("")
    print(f"{len(reprize):,} meciuri cu cartonase pe reprize, "
          f"{len(intreg):,} cu cartonase pe meci intreg")
    return reprize, intreg


def _fit(train: pd.DataFrame, col_h: str, col_a: str, azi: pd.Timestamp):
    echipe = sorted(set(train["home"]) | set(train["away"]))
    idx = {t: i for i, t in enumerate(echipe)}
    varste = (azi - train["date"]).dt.days.to_numpy(dtype=float)
    return counts_model.fit_counts(
        train["home"].map(idx).to_numpy(), train["away"].map(idx).to_numpy(),
        train[col_h].to_numpy(dtype=float), train[col_a].to_numpy(dtype=float),
        np.exp(-XI * varste), len(echipe), idx)


def _dispersie(fit, train, col_h, col_a, scara=1.0):
    medii, obs = [], []
    for r in train.itertuples(index=False):
        rate = fit.rates(r.home, r.away)
        if rate:
            medii.append((rate[0] + rate[1]) * scara)
            obs.append(float(getattr(r, col_h)) + float(getattr(r, col_a)))
    if len(medii) < 150:
        return None
    return counts_model.fit_dispersie(np.array(medii), np.array(obs))


def evalueaza(reprize: pd.DataFrame, intreg: pd.DataFrame) -> dict:
    rez = {nume: {l: [] for l in LINII} for nume in ("real", "baza", "A", "B")}
    rez["real_gazda"], rez["baza_gazda"], rez["A_gazda"], rez["B_gazda"] = [], [], [], []

    for div, liga in reprize.groupby("div", sort=True):
        liga = liga.sort_values("date").reset_index(drop=True)
        intreg_liga = intreg[intreg["div"] == div]
        if len(liga) < MINIM_REPRIZA * 2:
            continue
        start = liga["date"].min() + pd.Timedelta(days=330)
        for taiere in pd.date_range(start, liga["date"].max(), freq=f"{PAS_ZILE}D"):
            train_r = liga[liga["date"] < taiere]
            test = liga[(liga["date"] >= taiere)
                        & (liga["date"] < taiere + pd.Timedelta(days=PAS_ZILE))]
            train_i = intreg_liga[(intreg_liga["date"] < taiere)
                                  & (intreg_liga["date"]
                                     >= taiere - pd.Timedelta(days=FEREASTRA_ZILE))]
            if len(train_r) < MINIM_REPRIZA or len(train_i) < MINIM_INTREG or test.empty:
                continue

            # A: direct pe prima repriza.
            fit_a = _fit(train_r, "c1", "a1", taiere)
            k_a = _dispersie(fit_a, train_r, "c1", "a1")

            # B: meci intreg x partea din prima repriza.
            fit_b = _fit(train_i, "cy", "ca", taiere)
            parte = float((train_r["c1"] + train_r["a1"]).sum()
                          / max((train_r["c_tot"] + train_r["a_tot"]).sum(), 1))
            k_b = _dispersie(fit_b, train_r, "c1", "a1", scara=parte)
            if k_a is None or k_b is None:
                continue

            # Profilul arbitrilor, din meciul intreg (acolo sunt mult mai multe date).
            profil = {}
            for r in train_i.itertuples(index=False):
                if not r.referee:
                    continue
                rate = fit_b.rates(r.home, r.away)
                if rate:
                    p = profil.setdefault(r.referee, [0.0, 0.0])
                    p[0] += float(r.cy + r.ca)
                    p[1] += rate[0] + rate[1]

            total_r = (train_r["c1"] + train_r["a1"]).to_numpy()
            baza = {l: float(np.mean(total_r > l)) for l in LINII}
            baza_gazda = float(np.mean(train_r["c1"].to_numpy() > 0.5))

            for r in test.itertuples(index=False):
                rate_a = fit_a.rates(r.home, r.away)
                rate_b = fit_b.rates(r.home, r.away)
                if rate_a is None or rate_b is None:
                    continue
                factor = 1.0
                if r.referee in profil:
                    dat, asteptat = profil[r.referee]
                    factor = (dat + K_ARBITRU) / (asteptat + K_ARBITRU)

                medie_a = rate_a[0] + rate_a[1]
                medie_b = (rate_b[0] + rate_b[1]) * parte * factor
                d_a = counts_model.nb_pmf(medie_a, k_a)
                d_b = counts_model.nb_pmf(medie_b, k_b)
                total = float(r.c1 + r.a1)
                for l in LINII:
                    rez["real"][l].append(total > l)
                    rez["baza"][l].append(baza[l])
                    rez["A"][l].append(counts_model.peste(d_a, l))
                    rez["B"][l].append(counts_model.peste(d_b, l))

                # Gazda primeste cel putin un cartonas in prima repriza.
                rez["real_gazda"].append(r.c1 > 0.5)
                rez["baza_gazda"].append(baza_gazda)
                rez["A_gazda"].append(1 - float(np.exp(-rate_a[0])))
                rez["B_gazda"].append(1 - float(np.exp(-rate_b[0] * parte * factor)))
    return rez


def _ll(p, s):
    p = np.clip(np.array(p, dtype=float), 1e-6, 1 - 1e-6)
    s = np.array(s, dtype=bool)
    return -np.log(np.where(s, p, 1 - p))


def main() -> int:
    reprize, intreg = pregateste()
    rez = evalueaza(reprize, intreg)

    print(f"\n{'piata':<26}{'n':>7}{'real':>8}{'baza':>10}{'A direct':>10}"
          f"{'B intreg':>10}{'castig B':>10}{'t':>8}")
    piete = [(f"peste {l} in repriza 1", rez["real"][l], rez["baza"][l],
              rez["A"][l], rez["B"][l]) for l in LINII]
    piete.append(("gazda primeste cartonas", rez["real_gazda"], rez["baza_gazda"],
                  rez["A_gazda"], rez["B_gazda"]))
    for nume, real, baza, a, b in piete:
        if len(real) < 200:
            continue
        ll_baza, ll_a, ll_b = _ll(baza, real), _ll(a, real), _ll(b, real)
        dif = ll_baza - ll_b
        t = dif.mean() / (dif.std(ddof=1) / np.sqrt(len(dif)))
        print(f"{nume:<26}{len(real):>7}{np.mean(real):>8.1%}{ll_baza.mean():>10.5f}"
              f"{ll_a.mean():>10.5f}{ll_b.mean():>10.5f}{dif.mean():>+10.5f}{t:>+8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
