"""Cat de bun e modelul de nationale, masurat inainte sa fie aratat cuiva.

Nu exista cote istorice pentru meciurile astea, deci nu se poate spune daca
bate piata. Se poate spune insa daca e mai bun decat a ghici ratele de baza --
si asta e pragul sub care o predictie nu are ce cauta in aplicatie.

Metoda: antrenare doar pe trecut, evaluare pe meciurile urmatoare, din trei in
trei luni. Nicio informatie din viitor nu ajunge in model.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import national_model
from fetch_national import incarca

# Doar competitiile cu teren real, ca la antrenament.
EVAL_START = "2023-01-01"
PAS_ZILE = 90


def _rezultat(hg: int, ag: int) -> int:
    return 0 if hg > ag else (1 if hg == ag else 2)


def evalueaza(hist: pd.DataFrame, xi: float) -> dict:
    hist = hist.sort_values("date").reset_index(drop=True)
    start = pd.Timestamp(EVAL_START)
    limite = pd.date_range(start, hist["date"].max(), freq=f"{PAS_ZILE}D")

    ll_model, ll_baza, corecte, n = [], [], 0, 0
    # (probabilitatea celei mai probabile piete 1X2, s-a adeverit?)
    selectii: list[tuple[float, bool]] = []
    # Ratele de baza: cat de des castiga gazda / egal / oaspete, in trecut.
    for taiere in limite:
        trecut = hist[hist["date"] < taiere]
        viitor = hist[(hist["date"] >= taiere)
                      & (hist["date"] < taiere + pd.Timedelta(days=PAS_ZILE))]
        if len(trecut) < 1000 or viitor.empty:
            continue

        baza = np.array([
            (trecut["hg"] > trecut["ag"]).mean(),
            (trecut["hg"] == trecut["ag"]).mean(),
            (trecut["hg"] < trecut["ag"]).mean(),
        ])
        model = national_model.fit(trecut, taiere, xi)
        if model is None:
            continue

        for r in viitor.itertuples(index=False):
            rez = national_model.probabilitati(model, r.home, r.away)
            if rez is None:
                continue
            p = rez["probs"]
            vector = np.array([p["p_home"], p["p_draw"], p["p_away"]])
            vector = np.clip(vector, 1e-6, 1)
            vector /= vector.sum()

            k = _rezultat(r.hg, r.ag)
            ll_model.append(-np.log(vector[k]))
            ll_baza.append(-np.log(baza[k]))
            corecte += int(np.argmax(vector) == k)
            n += 1

            # Cum s-ar comporta regula de selectie: cea mai probabila piata,
            # daca trece de 60%.
            cea_mai_buna = int(np.argmax(vector))
            if vector[cea_mai_buna] >= 0.60:
                selectii.append((float(vector[cea_mai_buna]), cea_mai_buna == k))

    if not n:
        return {"n": 0}
    return {
        "n": n,
        "log_loss": float(np.mean(ll_model)),
        "log_loss_baza": float(np.mean(ll_baza)),
        "acuratete": corecte / n,
        "selectii": selectii,
    }


# Benzile din recomandari.py, verificate aici pe nationale: o rata promisa pe
# meciuri de club n-are voie sa fie folosita la nationale fara sa fie masurata.
BENZI = [(0.80, 1.01, "80% sau peste"), (0.70, 0.80, "70-80%"),
         (0.65, 0.70, "65-70%"), (0.60, 0.65, "60-65%")]


def pe_benzi(selectii: list[tuple[float, bool]]) -> list[dict]:
    out = []
    for jos, sus, eticheta in BENZI:
        ale_benzii = [c for p, c in selectii if jos <= p < sus]
        if ale_benzii:
            out.append({"banda": eticheta, "n": len(ale_benzii),
                        "rata": sum(ale_benzii) / len(ale_benzii)})
    return out


def main() -> int:
    hist = incarca()
    if hist.empty:
        print("Lipsesc datele. Ruleaza fetch_national.py.")
        return 1
    print(f"{len(hist):,} meciuri, {hist['date'].min().date()} .. "
          f"{hist['date'].max().date()}\n")

    rezultate = {}
    for xi in (0.0004, 0.0006, 0.0008, 0.0012, 0.0020):
        r = evalueaza(hist, xi)
        rezultate[xi] = r
        if r["n"]:
            print(f"xi={xi:.4f}  n={r['n']:>5}  log-loss {r['log_loss']:.5f}  "
                  f"(baza {r['log_loss_baza']:.5f})  acuratete {r['acuratete']:.1%}")

    cel_mai_bun = min((r for r in rezultate.values() if r["n"]),
                      key=lambda r: r["log_loss"], default=None)
    if cel_mai_bun:
        castig = cel_mai_bun["log_loss_baza"] - cel_mai_bun["log_loss"]
        print(f"\nCel mai bun: log-loss {cel_mai_bun['log_loss']:.5f}, "
              f"cu {castig:+.5f} fata de ratele de baza.")
        if castig <= 0:
            print("ATENTIE: modelul nu bate ghicitul. Nu-l pune in aplicatie.")

        print("\nCum s-ar comporta regula de selectie (fara filtrul de cote, "
              "care nu se poate verifica in trecut):")
        for b in pe_benzi(cel_mai_bun["selectii"]):
            print(f"  {b['banda']:<14} {b['n']:>4} selectii  "
                  f"rata reala {b['rata']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
