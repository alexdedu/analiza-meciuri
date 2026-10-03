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
        # Probabilitatile brute, inainte de calibrare, pentru comparatie.
        self.p_brut: list[float] = []

    def adauga(self, p: float, s: bool, p_brut: float | None = None) -> None:
        self.p.append(float(p))
        self.s.append(bool(s))
        self.p_brut.append(float(p_brut if p_brut is not None else p))

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

    # Calibrarea se invata din predictiile deja verificate, deci nu foloseste
    # niciodata viitorul: pana se aduna destule, se merge necalibrat.
    istoric_cal: dict[str, list[tuple[float, bool]]] = {}
    calibrari: dict[str, tuple[float, float]] = {}
    MINIM_CALIBRARE = 400

    def masura(nume: str) -> Masura:
        return masuri.setdefault(nume, Masura(nume))

    def pune(nume: str, p: float, s: bool) -> None:
        """Noteaza o predictie, calibrata cu ce s-a invatat pana acum."""
        baza_gamma = calibrari.get(nume)
        p_cal = (float(counts_model.calibreaza(p, *baza_gamma))
                 if baza_gamma else p)
        masura(nume).adauga(p_cal, s, p_brut=p)
        istoric_cal.setdefault(nume, []).append((p, s))

    def reinvata_calibrarea() -> None:
        for nume, perechi in istoric_cal.items():
            if len(perechi) < MINIM_CALIBRARE:
                continue
            p = np.array([x for x, _ in perechi])
            s = np.array([float(y) for _, y in perechi])
            calibrari[nume] = counts_model.fit_calibrare(p, s)

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

        # Dispersia, invatata doar din trecut, separat pentru fiecare parte.
        # Poisson presupune ca varianta e egala cu media, ceea ce la cornere nu
        # e adevarat: unele meciuri "se aprind". De aici venea increderea
        # umflata a modelului.
        medii_t, obs_t, medii_h, obs_h, medii_a, obs_a = [], [], [], [], [], []
        for r in train.itertuples(index=False):
            rate = fit.rates(r.home, r.away)
            if rate is None:
                continue
            h_obs = float(getattr(r, coloane[0]))
            a_obs = float(getattr(r, coloane[1]))
            medii_t.append(rate[0] + rate[1])
            obs_t.append(h_obs + a_obs)
            medii_h.append(rate[0])
            obs_h.append(h_obs)
            medii_a.append(rate[1])
            obs_a.append(a_obs)
        if len(medii_t) < 200:
            continue
        k_total = counts_model.fit_dispersie(np.array(medii_t), np.array(obs_t))
        k_home = counts_model.fit_dispersie(np.array(medii_h), np.array(obs_h))
        k_away = counts_model.fit_dispersie(np.array(medii_a), np.array(obs_a))

        for r in test.itertuples(index=False):
            rate = fit.rates(r.home, r.away)
            if rate is None:
                continue
            lam, mu = rate
            d = {"total": counts_model.nb_pmf(lam + mu, k_total),
                 "home": counts_model.nb_pmf(lam, k_home),
                 "away": counts_model.nb_pmf(mu, k_away)}
            h = float(getattr(r, coloane[0]))
            a = float(getattr(r, coloane[1]))

            for linie in etichete["total"]:
                p_peste = counts_model.peste(d["total"], linie)
                pune(f"total peste {linie}", p_peste, h + a > linie)
                # Partea de "sub" se masoara separat: calibrarea verificata la
                # 60-70% pentru "peste" nu spune nimic despre 60-70% la "sub",
                # care e cu totul alta zona a distributiei.
                pune(f"total sub {linie}", 1 - p_peste, h + a < linie)
            for linie in etichete.get("echipa", []):
                pune(f"gazda peste {linie}",
                     counts_model.peste(d["home"], linie), h > linie)
                pune(f"oaspete peste {linie}",
                     counts_model.peste(d["away"], linie), a > linie)

            if etichete.get("cine"):
                c = counts_model.cine_mai_multe(lam, mu, k_home, k_away)
                pune("mai multe gazda", c["home"], h > a)
                pune("mai multe oaspete", c["away"], a > h)

        reinvata_calibrarea()

    masuri["__calibrari__"] = calibrari  # type: ignore[assignment]
    return masuri


PRAGURI_SELECTIE = (0.60, 0.65, 0.70, 0.75)

# Banda din care se aleg efectiv selectiile: destul de probabil ca sa merite,
# destul de incert ca sa plateasca ceva (cota corecta intre 1,43 si 1,67).
BANDA_SELECTIE = (0.60, 0.70)


def raport_selectie(acumulat: dict[str, Masura]) -> None:
    """Cum s-ar comporta o selectie facuta doar pe increderea modelului.

    Pentru cornere si cartonase nu exista cote nicaieri -- nici istorice, nici
    pentru meciurile viitoare -- deci filtrul de acord cu piata, care face
    selectiile de la 1X2 sa tina, nu se poate aplica aici. Ramane intrebarea
    goala: cand modelul spune 70%, se intampla in 70% din cazuri?
    """
    print(f"\n{'piata':<22}{'prag':>6}{'n':>7}{'promis':>9}{'realizat':>10}{'eroare':>9}")
    for nume, m in acumulat.items():
        if len(m.p) < 200:
            continue
        p = np.array(m.p)
        s = np.array(m.s, dtype=float)
        for prag in PRAGURI_SELECTIE:
            alese = p >= prag
            if alese.sum() < 100:
                continue
            promis = p[alese].mean()
            realizat = s[alese].mean()
            print(f"{nume:<22}{prag:>6.0%}{int(alese.sum()):>7}"
                  f"{promis:>9.1%}{realizat:>10.1%}{realizat - promis:>+9.1%}")

        jos, sus = BANDA_SELECTIE
        in_banda = (p >= jos) & (p <= sus)
        if in_banda.sum() >= 100:
            print(f"{nume:<22}{'banda':>6}{int(in_banda.sum()):>7}"
                  f"{p[in_banda].mean():>9.1%}{s[in_banda].mean():>10.1%}"
                  f"{s[in_banda].mean() - p[in_banda].mean():>+9.1%}")


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
        gamma_pe_liga: dict[str, list[tuple[float, float]]] = {}
        ligi = 0
        for div, liga in df.groupby("div", sort=True):
            if liga[list(coloane)].notna().sum().min() < MINIM_MECIURI:
                continue
            ligi += 1
            rezultat = evalueaza(liga, coloane, etichete)
            for cheie, valoare in rezultat.pop("__calibrari__", {}).items():
                gamma_pe_liga.setdefault(cheie, []).append(valoare)
            for cheie, m in rezultat.items():
                tinta = acumulat.setdefault(cheie, Masura(cheie))
                tinta.p.extend(m.p)
                tinta.s.extend(m.s)
                tinta.p_brut.extend(m.p_brut)

        print(f"\n=== {nume} ({ligi} campionate)")
        print(f"{'piata':<22}{'n':>7}{'real':>8}{'log-loss':>10}"
              f"{'baza':>9}{'castig':>9}{'calibrare':>11}")
        for m in acumulat.values():
            r = m.raport()
            if r:
                print(f"{r['piata']:<22}{r['n']:>7}{r['rata_reala']:>8.1%}"
                      f"{r['log_loss']:>10.5f}{r['log_loss_baza']:>9.5f}"
                      f"{r['castig']:>+9.5f}{r['ece']:>11.4f}")

        print(f"\n--- {nume}: cum s-ar comporta o selectie pe incredere")
        raport_selectie(acumulat)

        # Factorii invatati, ca sa poata fi dusi in productie ca numere fixe.
        print(f"\n--- {nume}: calibrarea invatata (mediana pe campionate)")
        for cheie, valori in sorted(gamma_pe_liga.items()):
            baze = np.median([b for b, _ in valori])
            gamma = np.median([g for _, g in valori])
            print(f"    {cheie:<22} baza {baze:.3f}  gamma {gamma:.3f}  "
                  f"({len(valori)} campionate)")

    print(f"\nDurata: {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
