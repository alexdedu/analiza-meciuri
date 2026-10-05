"""Ajuta arbitrul la prezicerea cartonaselor? Masurat, nu presupus.

Modelul de cartonase de acum stie doar cine joaca: cat de des ia cartonase
fiecare echipa si cat de des le provoaca adversarilor. Nu stie cine arbitreaza,
desi diferentele dintre arbitri sunt mari -- unii impart in medie trei
cartonase pe meci, altii sase.

Cum intra arbitrul: un factor multiplicativ, cat da el fata de cat ar fi fost
de asteptat cu echipele pe care le-a avut. Un arbitru cu cinci meciuri la activ
n-are inca un profil, deci factorul e tras spre 1 cu o greutate echivalenta cu
K cartonase "neutre" -- cu cat are mai multe meciuri, cu atat conteaza mai mult
propriul lui istoric.

Comparatia e cinstita: acelasi model, aceeasi dispersie, aceleasi meciuri,
singura diferenta e factorul arbitrului. Totul invatat doar din trecut.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import counts_model
from data_loader import load_all
from fetch_referees import incarca as incarca_arbitri

XI = 0.0025
FEREASTRA_ZILE = 1095
PAS_ZILE = 14
START_EVALUARE = pd.Timestamp("2022-08-01")
MINIM_MECIURI = 300

LINII = [2.5, 3.5, 4.5, 5.5]
PRIORI_CARTONASE = (80.0, 120.0, 160.0)   # greutatea "neutra" testata


def pregateste() -> pd.DataFrame:
    hist = load_all()
    numeric = {c: pd.to_numeric(hist[c], errors="coerce") for c in ("hy", "ay", "hr", "ar")}
    hist = hist.assign(cy=numeric["hy"] + numeric["hr"], ca=numeric["ay"] + numeric["ar"])
    hist = hist.dropna(subset=["cy", "ca"])

    arbitri = incarca_arbitri()
    arbitri = arbitri[(arbitri["referee"] != "") & (arbitri["home"] != "")]
    arbitri["date"] = arbitri["date"].dt.normalize()
    d = hist.merge(arbitri[["div", "date", "home", "away", "referee"]],
                   on=["div", "date", "home", "away"], how="inner")
    print(f"{len(hist):,} meciuri cu cartonase, {len(d):,} dintre ele cu arbitru cunoscut")
    return d


def _ll(p: np.ndarray, s: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(np.mean(-np.log(np.where(s, p, 1 - p))))


def evalueaza(df: pd.DataFrame) -> dict:
    """Pentru fiecare linie: probabilitati fara arbitru si cu arbitru."""
    rezultate = {"real": {l: [] for l in LINII}, "fara": {l: [] for l in LINII}}
    for k in PRIORI_CARTONASE:
        rezultate[k] = {l: [] for l in LINII}

    for div, liga in df.groupby("div", sort=True):
        liga = liga.sort_values("date").reset_index(drop=True)
        if len(liga) < MINIM_MECIURI:
            continue
        start = max(START_EVALUARE, liga["date"].min() + pd.Timedelta(days=FEREASTRA_ZILE // 2))
        for taiere in pd.date_range(start, liga["date"].max(), freq=f"{PAS_ZILE}D"):
            train = liga[(liga["date"] < taiere)
                         & (liga["date"] >= taiere - pd.Timedelta(days=FEREASTRA_ZILE))]
            test = liga[(liga["date"] >= taiere)
                        & (liga["date"] < taiere + pd.Timedelta(days=PAS_ZILE))]
            if len(train) < MINIM_MECIURI or test.empty:
                continue

            echipe = sorted(set(train["home"]) | set(train["away"]))
            idx = {t: i for i, t in enumerate(echipe)}
            varste = (taiere - train["date"]).dt.days.to_numpy(dtype=float)
            fit = counts_model.fit_counts(
                train["home"].map(idx).to_numpy(), train["away"].map(idx).to_numpy(),
                train["cy"].to_numpy(dtype=float), train["ca"].to_numpy(dtype=float),
                np.exp(-XI * varste), len(echipe), idx)

            # Cat ar fi fost de asteptat in fiecare meci din trecut, si cat a
            # dat de fapt arbitrul lui.
            asteptat = np.array([sum(fit.rates(h, a) or (np.nan, np.nan))
                                 for h, a in zip(train["home"], train["away"])])
            observat = (train["cy"] + train["ca"]).to_numpy(dtype=float)
            ok = np.isfinite(asteptat)
            k_disp = counts_model.fit_dispersie(asteptat[ok], observat[ok])

            pe_arbitru = (pd.DataFrame({"ref": train["referee"].to_numpy()[ok],
                                        "obs": observat[ok], "exp": asteptat[ok]})
                          .groupby("ref").sum())

            for r in test.itertuples(index=False):
                rate = fit.rates(r.home, r.away)
                if rate is None:
                    continue
                medie = rate[0] + rate[1]
                total = float(r.cy + r.ca)
                dist_fara = counts_model.nb_pmf(medie, k_disp)

                for linie in LINII:
                    rezultate["real"][linie].append(total > linie)
                    rezultate["fara"][linie].append(counts_model.peste(dist_fara, linie))

                istoric_arbitru = (pe_arbitru.loc[r.referee]
                                   if r.referee in pe_arbitru.index else None)
                for k in PRIORI_CARTONASE:
                    if istoric_arbitru is None:
                        factor = 1.0
                    else:
                        factor = ((istoric_arbitru["obs"] + k)
                                  / (istoric_arbitru["exp"] + k))
                    dist = counts_model.nb_pmf(medie * factor, k_disp)
                    for linie in LINII:
                        rezultate[k][linie].append(counts_model.peste(dist, linie))
    return rezultate


def main() -> int:
    df = pregateste()
    rez = evalueaza(df)

    print(f"\n{'linie':<14}{'n':>7}{'fara arbitru':>14}"
          + "".join(f"{f'K={k:.0f}':>11}" for k in PRIORI_CARTONASE))
    for linie in LINII:
        s = np.array(rez["real"][linie])
        fara = _ll(np.array(rez["fara"][linie]), s)
        cu = [_ll(np.array(rez[k][linie]), s) for k in PRIORI_CARTONASE]
        print(f"peste {linie:<8}{len(s):>7}{fara:>14.5f}"
              + "".join(f"{v:>11.5f}" for v in cu))

    # Test pereche pentru cea mai buna greutate, pe linia cea mai jucata.
    print("\nCastig fata de modelul fara arbitru (pozitiv = mai bun), test pereche:")
    for linie in (3.5, 4.5):
        s = np.array(rez["real"][linie])

        def pe_meci(p):
            p = np.clip(np.array(p), 1e-6, 1 - 1e-6)
            return -np.log(np.where(s, p, 1 - p))

        fara = pe_meci(rez["fara"][linie])
        for k in PRIORI_CARTONASE:
            dif = fara - pe_meci(rez[k][linie])
            t = dif.mean() / (dif.std(ddof=1) / np.sqrt(len(dif)))
            print(f"  peste {linie}  K={k:<5.0f} castig {dif.mean():+.5f}  t={t:+6.2f}")

    # Selectiile pe cartonase se aleg din banda 60-70%, dupa calibrare. Factorul
    # arbitrului face procentele mai departate de medie, deci trebuie verificat
    # ca promisiunea ramane aproape de realitate si cu el.
    import predict_counts
    gamma = predict_counts.GAMMA["cards_total"]
    k = 120.0
    print(f"\nCalibrare in banda 60-70% (gamma {gamma}, K={k:.0f}):")
    for linie in (2.5, 3.5, 4.5):
        s = np.array(rez["real"][linie], dtype=float)
        baza = s.mean()
        for eticheta, brut in (("fara arbitru", rez["fara"][linie]),
                               ("cu arbitru", rez[k][linie])):
            for sens, p_brut, real in (("peste", np.array(brut), s),
                                       ("sub", 1 - np.array(brut), 1 - s)):
                b = baza if sens == "peste" else 1 - baza
                p = counts_model.calibreaza(p_brut, b, gamma)
                in_banda = (p >= 0.60) & (p <= 0.70)
                if in_banda.sum() < 200:
                    continue
                print(f"  {sens} {linie} {eticheta:<13} n={int(in_banda.sum()):>5}  "
                      f"promis {p[in_banda].mean():.1%}  realizat {real[in_banda].mean():.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
