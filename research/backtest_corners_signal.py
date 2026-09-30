"""Ajuta cornerele la prezicerea rezultatului? Masurat, nu presupus.

Ideea: modelul de acum combina doua estimari ale fortei unei echipe -- din
goluri si din suturi pe poarta. Suturile ajuta pentru ca sunt de zece ori mai
numeroase decat golurile, deci masoara mai stabil. Cornerele sunt si ele un semn
de dominare teritoriala si sunt la fel de numeroase, deci merita intrebat daca
adauga ceva peste ce stiu deja golurile si suturile.

Raspunsul poate foarte bine sa fie "nu": cornerele vin adesea din atacuri
sterile, iar informatia lor poate fi deja continuta in suturi. De aceea se
masoara inainte sa se schimbe ceva in aplicatie.

Metoda: acelasi mers inainte in timp ca backtest_xg.py, dar cu un al treilea
model, pe cornere. Se compara log-loss-ul amestecului de doua cu al celui de
trei, pe aceleasi meciuri.
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from backtest import BURN_IN_DAYS, REFIT_DAYS, WINDOW_DAYS
from backtest_xg import XI, fit_on
from data_loader import load_all
from dixon_coles import markets_from_rates

# Doar campionatele care au cornere in arhiva.
LIGI = {"E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1", "SC0", "G1", "T1"}
SPLIT = pd.Timestamp("2019-07-01")


def ruleaza() -> pd.DataFrame:
    df = load_all()
    df = df[df["div"].isin(LIGI)]
    randuri = []
    t0 = time.time()

    for div, liga in df.groupby("div", sort=True):
        liga = liga.sort_values("date").reset_index(drop=True)
        start = liga["date"].min() + pd.Timedelta(days=BURN_IN_DAYS)
        dates = liga["date"].to_numpy()
        fit_g = fit_s = fit_c = None
        conv_s, conv_c = 0.33, 0.10
        ultimul = None
        warm_g: dict = {}
        warm_s: dict = {}
        warm_c: dict = {}
        n = 0

        for _, meci in liga.iterrows():
            azi = meci["date"]
            if azi < start:
                continue

            if ultimul is None or (azi - ultimul).days >= REFIT_DAYS:
                train = liga[(dates < np.datetime64(azi))
                             & (dates >= np.datetime64(azi - pd.Timedelta(days=WINDOW_DAYS)))]
                if len(train) < 150:
                    continue
                echipe = sorted(set(train["home"]) | set(train["away"]))
                idx = {t: k for k, t in enumerate(echipe)}
                k = len(echipe)
                fit_g, warm_g = fit_on(train, azi, ("hg", "ag"), XI, warm_g, echipe, idx, k)
                fit_s, warm_s = fit_on(train, azi, ("hst", "ast"), XI, warm_s, echipe, idx, k)
                fit_c, warm_c = fit_on(train, azi, ("hc", "ac"), XI, warm_c, echipe, idx, k)

                suturi = train.dropna(subset=["hst", "ast"])
                if len(suturi) > 100:
                    total = suturi["hst"].sum() + suturi["ast"].sum()
                    if total > 0:
                        conv_s = float((suturi["hg"].sum() + suturi["ag"].sum()) / total)
                cornere = train.dropna(subset=["hc", "ac"])
                if len(cornere) > 100:
                    total = cornere["hc"].sum() + cornere["ac"].sum()
                    if total > 0:
                        # Cate goluri revin, in medie, unui corner. Nu e o
                        # relatie cauzala, e doar aducerea pe aceeasi scara.
                        conv_c = float((cornere["hg"].sum() + cornere["ag"].sum()) / total)
                ultimul = azi

            if fit_g is None or meci["home"] not in fit_g.teams or meci["away"] not in fit_g.teams:
                continue
            lam_g, mu_g = fit_g.rates(meci["home"], meci["away"])

            if fit_s is not None and meci["home"] in fit_s.teams:
                ls, ms = fit_s.rates(meci["home"], meci["away"])
                lam_s, mu_s = ls * conv_s, ms * conv_s
            else:
                lam_s, mu_s = lam_g, mu_g

            if fit_c is not None and meci["home"] in fit_c.teams:
                lc, mc = fit_c.rates(meci["home"], meci["away"])
                lam_c, mu_c = lc * conv_c, mc * conv_c
            else:
                lam_c, mu_c = lam_g, mu_g

            randuri.append({
                "div": div, "date": azi, "result": meci["result"],
                "over25": meci["over25"],
                "lam_g": lam_g, "mu_g": mu_g, "lam_s": lam_s, "mu_s": mu_s,
                "lam_c": lam_c, "mu_c": mu_c, "rho": fit_g.rho,
            })
            n += 1
        print(f"  {div:4s} {n:6,} predictii ({time.time() - t0:5.1f}s)", flush=True)

    return pd.DataFrame(randuri)


def log_loss(d: pd.DataFrame, greutati: tuple[float, float, float]) -> dict:
    """Log-loss pentru 1X2 si peste/sub 2.5, la o combinatie de greutati."""
    wg, ws, wc = greutati
    lam = np.exp(wg * np.log(d["lam_g"]) + ws * np.log(d["lam_s"]) + wc * np.log(d["lam_c"]))
    mu = np.exp(wg * np.log(d["mu_g"]) + ws * np.log(d["mu_s"]) + wc * np.log(d["mu_c"]))

    ll_1x2, ll_ou = [], []
    for l, m, r, rez, ou in zip(lam, mu, d["rho"], d["result"], d["over25"]):
        p = markets_from_rates(float(l), float(m), float(r))
        vector = np.clip([p["p_home"], p["p_draw"], p["p_away"]], 1e-9, 1)
        vector = vector / vector.sum()
        ll_1x2.append(-np.log(vector[int(rez)]))
        p_over = min(max(p["p_over25"], 1e-9), 1 - 1e-9)
        ll_ou.append(-np.log(p_over if ou == 1 else 1 - p_over))
    return {"1x2": float(np.mean(ll_1x2)), "ou": float(np.mean(ll_ou))}


def main() -> int:
    cale = "out/rates_triple.csv"
    try:
        d = pd.read_csv(cale, parse_dates=["date"])
        print(f"Refolosesc {cale} ({len(d):,} predictii)")
    except FileNotFoundError:
        d = ruleaza()
        d.to_csv(cale, index=False)
        print(f"\n{len(d):,} predictii salvate in {cale}")

    d = d[d["date"] >= SPLIT].dropna(subset=["lam_g", "lam_s", "lam_c"])
    print(f"\nEvaluare pe {len(d):,} meciuri de dupa {SPLIT.date()}\n")

    combinatii = [
        ("doar goluri", (1.0, 0.0, 0.0)),
        ("goluri + suturi (modelul de acum)", (0.50, 0.50, 0.0)),
        ("goluri + suturi + cornere", (0.45, 0.40, 0.15)),
        ("goluri + suturi + cornere", (0.40, 0.40, 0.20)),
        ("goluri + suturi + cornere", (0.35, 0.35, 0.30)),
        ("goluri + cornere", (0.50, 0.0, 0.50)),
        ("doar cornere", (0.0, 0.0, 1.0)),
    ]
    print(f"{'combinatie':<38}{'greutati':<20}{'log-loss 1X2':>14}{'peste/sub':>12}")
    for nume, g in combinatii:
        r = log_loss(d, g)
        print(f"{nume:<38}{str(g):<20}{r['1x2']:>14.5f}{r['ou']:>12.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
