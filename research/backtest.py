"""Backtest walk-forward: antrenez doar pe meciuri ANTERIOARE fiecarei predictii.

Protocol:
  - pentru fiecare liga, parcurg meciurile cronologic
  - reantrenez modelul o data pe saptamana, pe fereastra ultimelor ~3 sezoane
  - prezic fiecare meci inainte sa se joace, salvez probabilitatile
  - compar cu probabilitatile implicite din cotele de inchidere (piata)

Zero data leak: niciun meci nu contribuie la propria predictie.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import pandas as pd

from data_loader import load_all
from dixon_coles import fit_dixon_coles

WINDOW_DAYS = 1095   # ~3 sezoane de istoric in antrenare
REFIT_DAYS = 7       # reantrenare saptamanala
BURN_IN_DAYS = 550   # nu prezic pana nu am ~1.5 sezoane de date


def run(xi: float, verbose: bool = True) -> pd.DataFrame:
    df = load_all()
    rows = []
    t0 = time.time()

    for div, league in df.groupby("div", sort=True):
        league = league.sort_values("date").reset_index(drop=True)
        start_date = league["date"].min() + pd.Timedelta(days=BURN_IN_DAYS)
        dates = league["date"].to_numpy()
        fit = None
        last_fit = None
        last_params: dict[str, tuple[float, float]] = {}
        n_pred = 0

        for i, match in league.iterrows():
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
                age = (today - train["date"]).dt.days.to_numpy(dtype=float)
                weights = np.exp(-xi * age)
                init = np.concatenate([
                    np.array([last_params.get(t, (0.0, 0.0))[0] for t in teams]),
                    np.array([last_params.get(t, (0.0, 0.0))[1] for t in teams]),
                    [fit.home_adv if fit else 0.25, fit.rho if fit else -0.05],
                ])
                fit = fit_dixon_coles(
                    train["home"].map(idx).to_numpy(),
                    train["away"].map(idx).to_numpy(),
                    train["hg"].to_numpy(), train["ag"].to_numpy(),
                    weights, n, idx, init=init,
                )
                last_params = {t: (fit.attack[k], fit.defence[k]) for t, k in idx.items()}
                last_fit = today

            if fit is None or match["home"] not in fit.teams or match["away"] not in fit.teams:
                continue

            p = fit.markets(match["home"], match["away"])
            rows.append({
                "div": div, "season": match["season"], "date": today,
                "home": match["home"], "away": match["away"],
                "result": match["result"], "over25": match["over25"], "btts": match["btts"],
                **p,
                **{c: match[c] for c in (
                    "psc_h", "psc_d", "psc_a", "avg_h", "avg_d", "avg_a",
                    "max_h", "max_d", "max_a", "avg_o25", "avg_u25", "max_o25", "max_u25")},
            })
            n_pred += 1

        if verbose:
            print(f"  {div:4s} {n_pred:6,} predictii  ({time.time() - t0:5.1f}s)", flush=True)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--xi", type=float, default=0.0065)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    print(f"Backtest cu xi={args.xi} (jumatate de viata {np.log(2) / args.xi:.0f} zile)")
    preds = run(args.xi)
    out = args.out or f"out/preds_xi{args.xi}.csv"
    preds.to_csv(out, index=False)
    print(f"\n{len(preds):,} predictii salvate in {out}")
    sys.exit(0)
