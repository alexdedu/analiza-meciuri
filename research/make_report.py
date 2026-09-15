"""Genereaza raportul final de calibrare pentru modelul goluri+suturi."""
import numpy as np, pandas as pd
from evaluate import SPLIT, log_loss
from evaluate_xg import probs, market_probs

df = pd.read_csv("out/rates_dual.csv", parse_dates=["date"])
test = df[df["date"] >= SPLIT].reset_index(drop=True)
p = probs(test, 0.5)
y = test["result"].to_numpy(int)

print("Calibrare 1X2 — model goluri+suturi, 2019-2026")
print(f"{'interval':>12s} {'n':>8s} {'prezis':>8s} {'realizat':>9s} {'eroare':>8s}")
fp = p[:, :3].ravel()
fy = np.zeros((len(y), 3), int); fy[np.arange(len(y)), y] = 1; fy = fy.ravel()
rows = []
for b in range(10):
    s = np.clip((fp * 10).astype(int), 0, 9) == b
    if s.sum() < 50: continue
    print(f"  {b*10:3d}-{b*10+10:3d}%   {s.sum():8,} {fp[s].mean():8.3f} {fy[s].mean():9.3f} {fp[s].mean()-fy[s].mean():+8.3f}")
    rows.append((b, s.sum(), fp[s].mean(), fy[s].mean()))

ece = sum(n * abs(pr - re) for _, n, pr, re in rows) / sum(n for _, n, _, _ in rows)
print(f"\nEroare medie de calibrare (ECE): {ece:.4f}")
for name, col, truth in (("Over 2.5", 3, "over25"), ("BTTS", 4, "btts")):
    pc, yc = p[:, col], test[truth].to_numpy(int)
    print(f"{name:9s} prezis mediu {pc.mean():.3f} vs real {yc.mean():.3f}  "
          f"log-loss {-np.mean(np.log(np.clip(np.where(yc==1, pc, 1-pc),1e-15,1))):.5f}")
