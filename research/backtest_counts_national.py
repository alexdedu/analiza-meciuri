"""Cat de bine se prevad cornerele si cartonasele la echipele nationale.

Aceeasi disciplina ca la cluburi: nimic nu ajunge in aplicatie inainte sa fie
masurat pe meciuri pe care modelul nu le-a vazut. La cluburi, masuratoarea a
aratat ca totalul de cornere pe meci nu bate media campionatului -- e foarte
posibil sa iasa la fel si aici, si atunci asa va scrie.

Deosebirea fata de cluburi: nationalele joaca rar (~10 meciuri pe an), deci
fereastra de antrenare e mult mai lunga si uitarea mult mai lenta.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import counts_model
from fetch_national_stats import incarca

XI = 0.0006            # aceeasi uitare ca la modelul de rezultate
PAS_ZILE = 90
MINIM_MECIURI = 400

LINII_CORNERE = [8.5, 9.5, 10.5, 11.5]
LINII_CARTONASE = [2.5, 3.5, 4.5, 5.5]


def _ll(p: float, s: bool) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -float(np.log(p if s else 1 - p))


class Masura:
    def __init__(self, nume: str) -> None:
        self.nume, self.p, self.s = nume, [], []

    def adauga(self, p: float, s: bool) -> None:
        self.p.append(float(p))
        self.s.append(bool(s))

    def raport(self) -> dict | None:
        if len(self.p) < 150:
            return None
        s = np.array(self.s, dtype=float)
        baza = s.mean()
        ll_model = float(np.mean([_ll(p, si) for p, si in zip(self.p, self.s)]))
        ll_baza = float(np.mean([_ll(baza, si) for si in self.s]))
        return {"piata": self.nume, "n": len(self.p), "real": baza,
                "log_loss": ll_model, "baza": ll_baza,
                "castig": ll_baza - ll_model}


def evalueaza(df: pd.DataFrame, coloane: tuple[str, str], linii: list[float],
              cine: bool, ridge: float = 0.0) -> dict[str, Masura]:
    masuri: dict[str, Masura] = {}

    def m(nume: str) -> Masura:
        return masuri.setdefault(nume, Masura(nume))

    df = df.dropna(subset=list(coloane)).sort_values("date").reset_index(drop=True)
    start = df["date"].min() + pd.Timedelta(days=730)
    for taiere in pd.date_range(start, df["date"].max(), freq=f"{PAS_ZILE}D"):
        train = df[df["date"] < taiere]
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
            np.exp(-XI * varste), len(echipe), idx, ridge=ridge)

        # Dispersia totalului, invatata tot din trecut.
        medii, observate = [], []
        for r in train.itertuples(index=False):
            rate = fit.rates(r.home, r.away)
            if rate:
                medii.append(sum(rate))
                observate.append(float(getattr(r, coloane[0]))
                                 + float(getattr(r, coloane[1])))
        if len(medii) < 200:
            continue
        k = counts_model.fit_dispersie(np.array(medii), np.array(observate))

        for r in test.itertuples(index=False):
            rate = fit.rates(r.home, r.away)
            if rate is None:
                continue
            lam, mu = rate
            nb = counts_model.nb_pmf(lam + mu, k)
            dist = counts_model.distributii(lam, mu)
            h = float(getattr(r, coloane[0]))
            a = float(getattr(r, coloane[1]))

            for linie in linii:
                m(f"total peste {linie}").adauga(
                    counts_model.peste(nb, linie), h + a > linie)
            for linie in (3.5, 4.5):
                m(f"gazda peste {linie}").adauga(
                    counts_model.peste(dist["home"], linie), h > linie)
                m(f"oaspete peste {linie}").adauga(
                    counts_model.peste(dist["away"], linie), a > linie)
            if cine:
                c = counts_model.cine_mai_multe(lam, mu)
                m("mai multe gazda").adauga(c["home"], h > a)
                m("mai multe oaspete").adauga(c["away"], a > h)
    return masuri


def main() -> int:
    df = incarca(doar_utile=True)
    if df.empty:
        print("Lipsesc statisticile. Ruleaza fetch_national_stats.py.")
        return 1
    df = df.assign(cy=df["hy"].astype(float) + df["hr"].astype(float),
                   ca=df["ay"].astype(float) + df["ar"].astype(float))
    print(f"{len(df):,} meciuri cu statistici, "
          f"{df['date'].min().date()} .. {df['date'].max().date()}")

    # Cu ~12 meciuri pe echipa, fortele libere sunt in mare parte zgomot.
    # Franarea catre medie e singura sansa ca modelul sa bata media.
    for ridge in (0.0, 10.0, 50.0, 200.0, 1000.0):
        for nume, coloane, linii, cine in (
                ("CORNERE", ("hc", "ac"), LINII_CORNERE, True),
                ("CARTONASE", ("cy", "ca"), LINII_CARTONASE, False)):
            rapoarte = [m.raport() for m in
                        evalueaza(df, coloane, linii, cine, ridge).values()]
            rapoarte = [r for r in rapoarte if r]
            if not rapoarte:
                continue
            mediu = sum(r["castig"] for r in rapoarte) / len(rapoarte)
            cel_mai_bun = max(rapoarte, key=lambda r: r["castig"])
            print(f"ridge={ridge:>7.0f}  {nume:<10} castig mediu {mediu:>+9.5f}"
                  f"  | cel mai bun: {cel_mai_bun['piata']} "
                  f"{cel_mai_bun['castig']:+.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
