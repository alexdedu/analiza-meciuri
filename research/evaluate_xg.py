"""Cauta ponderea optima goluri/suturi pe validare, apoi masoara pe test."""
from __future__ import annotations

import numpy as np
import pandas as pd

from dixon_coles import markets_from_rates
from evaluate import SPLIT, brier, devig, log_loss

df = pd.read_csv("out/rates_dual.csv", parse_dates=["date"])


def probs(d: pd.DataFrame, alpha: float) -> np.ndarray:
    """alpha = cat cantaresc golurile; 1-alpha = suturile pe poarta."""
    lam = np.exp(alpha * np.log(d["lam_g"]) + (1 - alpha) * np.log(d["lam_s"]))
    mu = np.exp(alpha * np.log(d["mu_g"]) + (1 - alpha) * np.log(d["mu_s"]))
    out = np.empty((len(d), 5))
    for i, (l, m, r) in enumerate(zip(lam, mu, d["rho"])):
        p = markets_from_rates(float(l), float(m), float(r))
        out[i] = [p["p_home"], p["p_draw"], p["p_away"], p["p_over25"], p["p_btts"]]
    return out


def market_probs(d):
    o = d[["psc_h", "psc_d", "psc_a"]].to_numpy(float)
    o = np.where(np.isnan(o), d[["avg_h", "avg_d", "avg_a"]].to_numpy(float), o)
    ok = np.isfinite(o).all(axis=1) & (o > 1).all(axis=1)
    mk = np.full((len(d), 3), np.nan)
    mk[ok] = devig(o[ok])
    return mk, ok


val = df[df["date"] < SPLIT].reset_index(drop=True)
test = df[df["date"] >= SPLIT].reset_index(drop=True)

print("=" * 70)
print("Cautare pondere goluri vs suturi (VALIDARE 2015-2019)")
print("=" * 70)
yv = val["result"].to_numpy(int)
best, best_ll = None, 9e9
for a in (0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0):
    ll = log_loss(probs(val, a)[:, :3], yv)
    flag = ""
    if ll < best_ll:
        best_ll, best, flag = ll, a, ""
    print(f"  goluri {a:4.0%} / suturi {1 - a:4.0%}   log-loss {ll:.5f}")
print(f"\n  -> optim: goluri {best:.0%} / suturi {1 - best:.0%}")

print("\n" + "=" * 70)
print("TEST CURAT 2019-2026")
print("=" * 70)
yt = test["result"].to_numpy(int)
mk, ok = market_probs(test)
p_new = probs(test, best)[:, :3]
p_old = probs(test, 1.0)[:, :3]

print(f"{'':28s} {'log-loss':>10s} {'Brier':>9s} {'acuratete':>10s}")
for name, p in (("DC doar goluri", p_old), (f"DC goluri+suturi", p_new),
                ("Piata (cote inchidere)", mk)):
    pp, yy = p[ok], yt[ok]
    print(f"{name:28s} {log_loss(pp, yy):10.5f} {brier(pp, yy):9.4f} {(pp.argmax(1) == yy).mean():9.2%}")

print("\nAdauga modelul informatie peste piata?")
m, k, yy = p_new[ok], mk[ok], yt[ok]
for w in (0.0, 0.05, 0.10, 0.15, 0.25, 0.40):
    p = np.exp(w * np.log(np.clip(m, 1e-12, 1)) + (1 - w) * np.log(np.clip(k, 1e-12, 1)))
    p /= p.sum(axis=1, keepdims=True)
    tag = "  <- doar piata" if w == 0 else ""
    print(f"  pondere model {w:4.0%}   log-loss {log_loss(p, yy):.5f}{tag}")

print("\nROI 1X2, miza fixa, cea mai buna cota de pe piata:")
odds = test[["max_h", "max_d", "max_a"]].to_numpy(float)[ok]
valid = np.isfinite(odds) & (odds > 1)
edge = m * odds - 1
won = np.zeros_like(valid)
won[np.arange(len(yy)), yy] = True
for thr in (0.0, 0.05, 0.10, 0.20):
    pick = valid & (edge > thr)
    if pick.sum() < 10:
        continue
    profit = np.where(won & pick, odds - 1, -1.0)[pick]
    se = profit.std(ddof=1) / np.sqrt(len(profit))
    print(f"  prag >{thr:4.0%}: {len(profit):6,} pariuri  ROI {profit.mean():+.2%}  t={profit.mean() / se:+.2f}")

print("\nOver/Under 2.5, cea mai buna cota:")
po = probs(test, best)[:, 3]
yo = test["over25"].to_numpy(int)
oo = test[["max_o25", "max_u25"]].to_numpy(float)
okk = np.isfinite(oo).all(axis=1)
mo = devig(oo[okk])[:, 0]
print(f"  log-loss model {-np.mean(np.log(np.clip(np.where(yo == 1, po, 1 - po), 1e-15, 1))):.5f}"
      f"  |  piata {-np.mean(np.log(np.clip(np.where(yo[okk] == 1, mo, 1 - mo), 1e-15, 1))):.5f}")
eo = np.column_stack([po * oo[:, 0], (1 - po) * oo[:, 1]]) - 1
wo = np.column_stack([yo == 1, yo == 0])
for thr in (0.0, 0.05, 0.10):
    pick = np.isfinite(oo) & (eo > thr)
    if pick.sum() < 10:
        continue
    profit = np.where(wo & pick, oo - 1, -1.0)[pick]
    se = profit.std(ddof=1) / np.sqrt(len(profit))
    print(f"  prag >{thr:4.0%}: {len(profit):6,} pariuri  ROI {profit.mean():+.2%}  t={profit.mean() / se:+.2f}")
