"""Cat de bune sunt predictiile pe cornere si cartonase. Masurat, nu presupus.

Lectia care a impus fisierul asta: la "ambele inscriu", unde nu exista cota cu
care sa confruntam modelul, el spunea 80% acolo unde realitatea era 59,8%. Deci
nicio piata noua nu intra in aplicatie inainte sa fie masurata pe date pe care
modelul nu le-a vazut.

Metoda: mers inainte in timp, campionat cu campionat. Modelul se reantreneaza
la fiecare doua saptamani doar pe trecut, apoi prezice meciurile urmatoare.
Se compara cu doua repere:
  - rata de baza (cat de des se intampla in general) -- pragul minim;
  - calibrarea (cand spune 70%, se intampla in 70% din cazuri?).
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

import counts_model
from data_loader import load_all

XI = 0.0025            # uitare: injumatatire la ~280 de zile
FEREASTRA_ZILE = 1095  # trei sezoane
PAS_ZILE = 14
START_EVALUARE = "2022-08-01"
MINIM_MECIURI = 300

LINII_CORNERE = [8.5, 9.5, 10.5, 11.5]
LINII_CORNERE_ECHIPA = [3.5, 4.5, 5.5]
LINII_CARTONASE = [2.5, 3.5, 4.5, 5.5]


def _ll(p: float, s: bool) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -np.log(p if s else 1 - p)


class Masura:
    """Aduna probabilitatile si ce s-a intamplat, pentru o piata."""

    def __init__(self, nume: str):
        self.nume = nume
        self.p: list[float] = []
        self.s: list[bool] = []

    def adauga(self, p: float, s: bool) -> None:
        self.p.append(float(p))
        self.s.append(bool(s))

    def raport(self) -> dict | None:
        if len(self.p) < 200:
            return None
        p = np.array(self.p)
        s = np.array(self.s, dtype=float)
        baza = s.mean()
        ll_model = float(np.mean([_ll(pi, si) for pi, si in zip(self.p, self.s)]))
        ll_baza = float(np.mean([_ll(baza, si) for si in self.s]))

        # Eroarea de calibrare: diferenta medie dintre ce spune si ce se intampla.
        ece, n = 0.0, len(p)
        for jos in np.arange(0.0, 1.0, 0.1):
            m = (p >= jos) & (p < jos + 0.1)
            if m.sum() >= 20:
                ece += m.sum() / n * abs(p[m].mean() - s[m].mean())

        return {"piata": self.nume, "n": n, "rata_reala": baza,
                "log_loss": ll_model, "log_loss_baza": ll_baza,
                "castig": ll_baza - ll_model, "ece": ece}


def evalueaza(df: pd.DataFrame, coloane: tuple[str, str], etichete: dict) -> dict:
    """Mers inainte in timp pe un singur campionat."""
    masuri: dict[str, Masura] = {}

    def masura(nume: str) -> Masura:
        return masuri.setdefault(nume, Masura(nume))

    df = df.dropna(subset=list(coloane)).sort_values("date").reset_index(drop=True)
    if len(df) < MINIM_MECIURI:
        return masuri

    start = max(pd.Timestamp(START_EVALUARE), df["date"].min()
                + pd.Timedelta(days=FEREASTRA_ZILE // 2))
    taieri = pd.date_range(start, df["date"].max(), freq=f"{PAS_ZILE}D")

    for taiere in taieri:
        train = df[(df["date"] < taiere)
                   & (df["date"] >= taiere - pd.Timedelta(days=FEREASTRA_ZILE))]
        test = df[(df["date"] >= taiere)
                  & (df["date"] < taiere + pd.Timedelta(days=PAS_ZILE))]
        if len(train) < MINIM_MECIURI or test.empty:
            continue

        echipe = sorted(set(train["home"]) | set(train["away"]))
        idx = {t: k for k, t in enumerate(echipe)}
        varste = (taiere - train["date"]).dt.days.to_numpy(dtype=float)
        fit = counts_model.fit_counts(
            train["home"].map(idx).to_numpy(), train["away"].map(idx).to_numpy(),
            train[coloane[0]].to_numpy(dtype=float),
            train[coloane[1]].to_numpy(dtype=float),
            np.exp(-XI * varste), len(echipe), idx)

        for r in test.itertuples(index=False):
            rate = fit.rates(r.home, r.away)
            if rate is None:
                continue
            lam, mu = rate
            d = counts_model.distributii(lam, mu)
            h = float(getattr(r, coloane[0]))
            a = float(getattr(r, coloane[1]))

            for linie in etichete["total"]:
                masura(f"total peste {linie}").adauga(
                    counts_model.peste(d["total"], linie), h + a > linie)
            for linie in etichete.get("echipa", []):
                masura(f"gazda peste {linie}").adauga(
                    counts_model.peste(d["home"], linie), h > linie)
                masura(f"oaspete peste {linie}").adauga(
                    counts_model.peste(d["away"], linie), a > linie)

            if etichete.get("cine"):
                c = counts_model.cine_mai_multe(lam, mu)
                masura("mai multe gazda").adauga(c["home"], h > a)
                masura("mai multe oaspete").adauga(c["away"], a > h)

    return masuri


def main() -> int:
    t0 = time.time()
    df = load_all()

    piete = {
        "CORNERE": (("hc", "ac"),
                    {"total": LINII_CORNERE, "echipa": LINII_CORNERE_ECHIPA,
                     "cine": True}),
        "CARTONASE": (("cy", "ay_total"),
                      {"total": LINII_CARTONASE, "echipa": [1.5, 2.5],
                       "cine": False}),
    }

    # Cartonasele se numara la un loc: galbene plus rosii. Feedul suplimentar
    # nu le are deloc, deci coloanele contin si valori lipsa.
    numeric = {c: pd.to_numeric(df[c], errors="coerce")
               for c in ("hy", "ay", "hr", "ar")}
    df = df.assign(cy=numeric["hy"] + numeric["hr"],
                   ay_total=numeric["ay"] + numeric["ar"])

    for nume, (coloane, etichete) in piete.items():
        acumulat: dict[str, Masura] = {}
        ligi = 0
        for div, liga in df.groupby("div", sort=True):
            if liga[list(coloane)].notna().sum().min() < MINIM_MECIURI:
                continue
            ligi += 1
            for cheie, m in evalueaza(liga, coloane, etichete).items():
                tinta = acumulat.setdefault(cheie, Masura(cheie))
                tinta.p.extend(m.p)
                tinta.s.extend(m.s)

        print(f"\n=== {nume} ({ligi} campionate)")
        print(f"{'piata':<22}{'n':>7}{'real':>8}{'log-loss':>10}"
              f"{'baza':>9}{'castig':>9}{'calibrare':>11}")
        for m in acumulat.values():
            r = m.raport()
            if r:
                print(f"{r['piata']:<22}{r['n']:>7}{r['rata_reala']:>8.1%}"
                      f"{r['log_loss']:>10.5f}{r['log_loss_baza']:>9.5f}"
                      f"{r['castig']:>+9.5f}{r['ece']:>11.4f}")

    print(f"\nDurata: {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
