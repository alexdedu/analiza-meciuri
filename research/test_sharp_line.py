"""Ipoteza alternativa: nu incerca sa bati piata -- foloseste piata.

Pinnacle e "casa ascutita": marja mica, accepta pariori profesionisti, linia ei
e cea mai apropiata de probabilitatea reala. Casele soft (majoritatea celor la
care paraiaza lumea) au uneori cote vizibil peste pretul corect al Pinnacle.

Strategie testata: pariez cand cea mai buna cota de pe piata depaseste pretul
corect Pinnacle (fara marja) cu un anumit prag. Niciun model, doar comparatie.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from evaluate import SPLIT, devig

df = pd.read_csv("out/rates_dual.csv", parse_dates=["date"])
test = df[df["date"] >= SPLIT].reset_index(drop=True)

sharp = test[["psc_h", "psc_d", "psc_a"]].to_numpy(float)
best = test[["max_h", "max_d", "max_a"]].to_numpy(float)
y = test["result"].to_numpy(int)

ok = np.isfinite(sharp).all(1) & (sharp > 1).all(1) & np.isfinite(best).all(1) & (best > 1).all(1)
sharp, best, y = sharp[ok], best[ok], y[ok]
fair = devig(sharp)                 # probabilitate corecta estimata de Pinnacle
fair_odds = 1.0 / fair              # cota corecta, fara marja
edge = best / fair_odds - 1.0       # cu cat e cea mai buna cota peste pretul corect

won = np.zeros(best.shape, dtype=bool)
won[np.arange(len(y)), y] = True

print("=" * 72)
print(f"Strategie: cota cea mai buna vs pret corect Pinnacle  ({len(y):,} meciuri 2019-2026)")
print("=" * 72)
print(f"{'prag':>6s} {'pariuri':>9s} {'ROI':>9s} {'t':>7s} {'cota med':>9s} {'rata castig':>12s}")
for thr in (0.00, 0.01, 0.02, 0.03, 0.05, 0.08):
    pick = edge > thr
    if pick.sum() < 30:
        continue
    profit = np.where(won & pick, best - 1.0, -1.0)[pick]
    se = profit.std(ddof=1) / np.sqrt(len(profit))
    print(f"{thr:>5.0%} {len(profit):9,} {profit.mean():+8.2%} {profit.mean() / se:+7.2f} "
          f"{best[pick].mean():9.2f} {won[pick].mean():11.1%}")

print("\nDefalcare pe liga la pragul >2%:")
pick = edge > 0.02
divs = test["div"].to_numpy()[ok]
rows = []
for d in sorted(set(divs)):
    sel = pick & (divs == d)[:, None]
    if sel.sum() < 50:
        continue
    profit = np.where(won & sel, best - 1.0, -1.0)[sel]
    se = profit.std(ddof=1) / np.sqrt(len(profit))
    rows.append({"liga": d, "pariuri": len(profit), "ROI": f"{profit.mean():+.2%}",
                 "t": f"{profit.mean() / se:+.2f}"})
print(pd.DataFrame(rows).to_string(index=False))

print("\nAtentie la interpretare: 'cea mai buna cota' inseamna cea mai buna dintre")
print("~40 de case la momentul inchiderii. Un pariar obisnuit, cu un singur cont,")
print("nu obtine acest pret. Testul arata unde exista teoretic valoare, nu un profit garantat.")
