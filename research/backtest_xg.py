"""Ca backtest.py, dar antreneaza DOUA modele si salveaza ratele brute.

Model A: Dixon-Coles pe goluri (semnal direct, dar zgomotos -- un gol deviat
         cantareste la fel ca o dominare clara).
Model B: Dixon-Coles pe suturi pe poarta, convertite in goluri asteptate.
         Suturile sunt un esantion de ~10x mai mare pe meci, deci estimeaza
         forta echipei mult mai stabil. E "xG-ul saracului", dar gratis.

Salvez ratele separat ca sa pot cauta ponderea optima offline, fara reantrenare.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from backtest import BURN_IN_DAYS, REFIT_DAYS, WINDOW_DAYS
from data_loader import load_all
from dixon_coles import fit_dixon_coles

XI = 0.0030  # ales pe perioada de validare in evaluate.py


def fit_on(train, today, value_cols, xi, warm, teams, idx, n):
    sub = train.dropna(subset=list(value_cols))
    if len(sub) < 150:
        return None, warm
    age = (today - sub["date"]).dt.days.to_numpy(dtype=float)
    init = np.concatenate([
        np.array([warm.get(t, (0.0, 0.0))[0] for t in teams]),
        np.array([warm.get(t, (0.0, 0.0))[1] for t in teams]),
        [0.25, -0.05],
    ])
    fit = fit_dixon_coles(
        sub["home"].map(idx).to_numpy(), sub["away"].map(idx).to_numpy(),
        sub[value_cols[0]].to_numpy().astype(int), sub[value_cols[1]].to_numpy().astype(int),
        np.exp(-xi * age), n, idx, init=init,
    )
    warm = {t: (fit.attack[k], fit.defence[k]) for t, k in idx.items()}
    return fit, warm


def main():
    df = load_all()
    rows = []
    t0 = time.time()

    for div, league in df.groupby("div", sort=True):
        league = league.sort_values("date").reset_index(drop=True)
        start_date = league["date"].min() + pd.Timedelta(days=BURN_IN_DAYS)
        dates = league["date"].to_numpy()
        fit_g = fit_s = None
        conv = 0.33
        last_fit = None
        warm_g: dict = {}
        warm_s: dict = {}
        n_pred = 0

        for _, match in league.iterrows():
            today = match["date"]
            if today < start_date:
                continue

            if last_fit is None or (today - last_fit).days >= REFIT_DAYS:
                train = league[(dates < np.datetime64(today))
                               & (dates >= np.datetime64(today - pd.Timedelta(days=WINDOW_DAYS)))]
                if len(train) < 150:
                    continue
                teams = sorted(set(train["home"]) | set(train["away"]))
                idx = {t: k for k, t in enumerate(teams)}
                n = len(teams)
                fit_g, warm_g = fit_on(train, today, ("hg", "ag"), XI, warm_g, teams, idx, n)
                fit_s, warm_s = fit_on(train, today, ("hst", "ast"), XI, warm_s, teams, idx, n)
                shots = train.dropna(subset=["hst", "ast"])
                if len(shots) > 100:
                    total_sot = shots["hst"].sum() + shots["ast"].sum()
                    if total_sot > 0:
                        conv = float((shots["hg"].sum() + shots["ag"].sum()) / total_sot)
                last_fit = today

            if fit_g is None or match["home"] not in fit_g.teams or match["away"] not in fit_g.teams:
                continue
            lam_g, mu_g = fit_g.rates(match["home"], match["away"])
            if fit_s is not None and match["home"] in fit_s.teams and match["away"] in fit_s.teams:
                ls, ms = fit_s.rates(match["home"], match["away"])
                lam_s, mu_s = ls * conv, ms * conv
            else:
                lam_s, mu_s = lam_g, mu_g

            rows.append({
                "div": div, "date": today, "home": match["home"], "away": match["away"],
                "result": match["result"], "over25": match["over25"], "btts": match["btts"],
                "lam_g": lam_g, "mu_g": mu_g, "lam_s": lam_s, "mu_s": mu_s,
                "rho": fit_g.rho,
                **{c: match[c] for c in (
                    "psc_h", "psc_d", "psc_a", "avg_h", "avg_d", "avg_a",
                    "max_h", "max_d", "max_a", "avg_o25", "avg_u25", "max_o25", "max_u25")},
            })
            n_pred += 1
        print(f"  {div:4s} {n_pred:6,} predictii  ({time.time() - t0:5.1f}s)", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv("out/rates_dual.csv", index=False)
    print(f"\n{len(out):,} predictii salvate in out/rates_dual.csv")


if __name__ == "__main__":
    main()
