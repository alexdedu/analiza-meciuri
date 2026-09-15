"""Evalueaza predictiile: model vs piata, calibrare, ROI.

Intrebarea centrala nu e "cate am ghicit", ci:
  1. modelul e mai bun decat cotele de inchidere? (log-loss / Brier)
  2. adauga informatie peste piata? (testul de blend)
  3. exista edge exploatabil dupa marja casei? (ROI cu prag)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SPLIT = pd.Timestamp("2019-07-01")  # inainte = validare (aleg xi), dupa = test curat


def devig(odds: np.ndarray) -> np.ndarray:
    """Scoate marja casei proportional -> probabilitati care insumeaza 1."""
    inv = 1.0 / odds
    return inv / inv.sum(axis=1, keepdims=True)


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1)).mean())


def brier(p: np.ndarray, y: np.ndarray) -> float:
    onehot = np.zeros_like(p)
    onehot[np.arange(len(y)), y] = 1
    return float(((p - onehot) ** 2).sum(axis=1).mean())


def prep(df: pd.DataFrame):
    model = df[["p_home", "p_draw", "p_away"]].to_numpy(float)
    model = model / model.sum(axis=1, keepdims=True)
    # cote de inchidere: Pinnacle (cea mai ascutita) cu rezerva pe media pietei
    o = df[["psc_h", "psc_d", "psc_a"]].to_numpy(float)
    fallback = df[["avg_h", "avg_d", "avg_a"]].to_numpy(float)
    o = np.where(np.isnan(o), fallback, o)
    ok = np.isfinite(o).all(axis=1) & (o > 1).all(axis=1)
    market = np.full_like(model, np.nan)
    market[ok] = devig(o[ok])
    return model, market, ok, df["result"].to_numpy(int)


def blend(model: np.ndarray, market: np.ndarray, w: float) -> np.ndarray:
    """Pool logaritmic: p ~ model^w * piata^(1-w)."""
    p = np.exp(w * np.log(np.clip(model, 1e-12, 1)) + (1 - w) * np.log(np.clip(market, 1e-12, 1)))
    return p / p.sum(axis=1, keepdims=True)


def roi_table(df: pd.DataFrame, model: np.ndarray, y: np.ndarray, price: str):
    cols = {"max": ["max_h", "max_d", "max_a"], "avg": ["avg_h", "avg_d", "avg_a"]}[price]
    odds = df[cols].to_numpy(float)
    valid = np.isfinite(odds) & (odds > 1)
    edge = model * odds - 1.0
    out = []
    for thr in (0.00, 0.03, 0.05, 0.10, 0.15, 0.20):
        pick = valid & (edge > thr)
        if pick.sum() == 0:
            continue
        won = np.zeros_like(pick)
        won[np.arange(len(y)), y] = True
        profit = np.where(won & pick, odds - 1.0, -1.0)[pick]
        n = len(profit)
        roi = profit.mean()
        se = profit.std(ddof=1) / np.sqrt(n)
        out.append({"prag": f">{thr:.0%}", "pariuri": n, "ROI": f"{roi:+.2%}",
                    "t": f"{roi / se:+.2f}" if se > 0 else "-",
                    "cota_med": f"{odds[pick].mean():.2f}"})
    return pd.DataFrame(out)


def main():
    print("=" * 74)
    print("PASUL 1 — alegerea xi pe perioada de VALIDARE (2015-2019)")
    print("=" * 74)
    scores = {}
    for path in sorted(Path("out").glob("preds_xi*.csv")):
        xi = path.stem.replace("preds_xi", "")
        df = pd.read_csv(path, parse_dates=["date"])
        val = df[df["date"] < SPLIT]
        model, market, ok, y = prep(val)
        scores[xi] = log_loss(model[ok], y[ok])
        print(f"  xi={xi:7s}  log-loss model = {scores[xi]:.5f}   (n={ok.sum():,})")
    best_xi = min(scores, key=scores.get)
    print(f"\n  -> aleg xi={best_xi}. De aici incolo, TOT se masoara pe 2019-2026, date nevazute.")

    df = pd.read_csv(f"out/preds_xi{best_xi}.csv", parse_dates=["date"])
    test = df[df["date"] >= SPLIT].reset_index(drop=True)
    model, market, ok, y = prep(test)
    m, mk, yy = model[ok], market[ok], y[ok]
    tst = test[ok].reset_index(drop=True)

    print("\n" + "=" * 74)
    print(f"PASUL 2 — model vs piata, pe {len(yy):,} meciuri din 2019-2026 (1X2)")
    print("=" * 74)
    print(f"{'':22s} {'log-loss':>10s} {'Brier':>9s} {'acuratete':>10s}")
    for name, p in (("Dixon-Coles", m), ("Piata (cote inchidere)", mk)):
        print(f"{name:22s} {log_loss(p, yy):10.5f} {brier(p, yy):9.4f} "
              f"{(p.argmax(1) == yy).mean():9.2%}")
    base = np.tile(np.bincount(yy, minlength=3) / len(yy), (len(yy), 1))
    print(f"{'Ghicit mereu 1 (baza)':22s} {log_loss(base, yy):10.5f} {brier(base, yy):9.4f} "
          f"{(yy == 0).mean():9.2%}")

    print("\n" + "=" * 74)
    print("PASUL 3 — adauga modelul informatie PESTE piata? (pool logaritmic)")
    print("=" * 74)
    for w in (0.0, 0.10, 0.20, 0.30, 0.50, 1.0):
        ll = log_loss(blend(m, mk, w), yy)
        tag = "  <- doar piata" if w == 0 else ("  <- doar model" if w == 1 else "")
        print(f"  pondere model {w:4.0%}   log-loss {ll:.5f}{tag}")

    print("\n" + "=" * 74)
    print("PASUL 4 — ROI real, miza fixa, cote de inchidere (1X2)")
    print("=" * 74)
    for price, label in (("max", "cea mai buna cota de pe piata (optimist)"),
                         ("avg", "cota medie a pietei (realist)")):
        print(f"\n  La {label}:")
        t = roi_table(tst, m, yy, price)
        print(t.to_string(index=False) if len(t) else "    niciun pariu peste prag")

    print("\n" + "=" * 74)
    print("PASUL 5 — Over/Under 2.5 si BTTS")
    print("=" * 74)
    po = tst["p_over25"].to_numpy(float)
    yo = tst["over25"].to_numpy(int)
    oo = tst[["max_o25", "max_u25"]].to_numpy(float)
    okk = np.isfinite(oo).all(axis=1)
    mkt_o = devig(oo[okk])[:, 0]
    ll_m = -np.mean(np.log(np.clip(np.where(yo == 1, po, 1 - po), 1e-15, 1)))
    ll_k = -np.mean(np.log(np.clip(np.where(yo[okk] == 1, mkt_o, 1 - mkt_o), 1e-15, 1)))
    print(f"  Over 2.5  log-loss model {ll_m:.5f}  |  piata {ll_k:.5f}  |  n={okk.sum():,}")
    edge_o = np.column_stack([po * tst["max_o25"], (1 - po) * tst["max_u25"]]) - 1
    won_o = np.column_stack([yo == 1, yo == 0])
    odds_o = tst[["max_o25", "max_u25"]].to_numpy(float)
    for thr in (0.0, 0.05, 0.10):
        pick = np.isfinite(odds_o) & (edge_o > thr)
        if pick.sum() == 0:
            continue
        profit = np.where(won_o & pick, odds_o - 1, -1.0)[pick]
        se = profit.std(ddof=1) / np.sqrt(len(profit))
        print(f"    prag >{thr:.0%}: {len(profit):,} pariuri, ROI {profit.mean():+.2%}, "
              f"t={profit.mean() / se:+.2f}")

    pb = tst["p_btts"].to_numpy(float)
    yb = tst["btts"].to_numpy(int)
    ll_b = -np.mean(np.log(np.clip(np.where(yb == 1, pb, 1 - pb), 1e-15, 1)))
    print(f"\n  BTTS      log-loss model {ll_b:.5f}  |  (fara cote in setul de date)")
    print(f"            prezis mediu {pb.mean():.3f} vs real {yb.mean():.3f}  -> "
          f"deviatie {abs(pb.mean() - yb.mean()):.3f}")

    print("\n" + "=" * 74)
    print("PASUL 6 — calibrare 1X2 (prezis vs realizat, pe decile)")
    print("=" * 74)
    flat_p = m.ravel()
    flat_y = np.zeros_like(m, dtype=int)
    flat_y[np.arange(len(yy)), yy] = 1
    flat_y = flat_y.ravel()
    bins = np.clip((flat_p * 10).astype(int), 0, 9)
    print(f"  {'interval':>12s} {'n':>8s} {'prezis':>8s} {'realizat':>9s} {'eroare':>8s}")
    for b in range(10):
        s = bins == b
        if s.sum() < 50:
            continue
        print(f"  {b * 10:3d}-{b * 10 + 10:3d}%   {s.sum():8,} {flat_p[s].mean():8.3f} "
              f"{flat_y[s].mean():9.3f} {flat_p[s].mean() - flat_y[s].mean():+8.3f}")


if __name__ == "__main__":
    sys.exit(main())
