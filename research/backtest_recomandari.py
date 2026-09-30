"""Ce fel de selectie automata se confirma istoric, si ce fel nu.

Aplicatia va avea o sectiune care alege singura cateva meciuri. Intrebarea nu e
"ce alegem", ci "ce alegere rezista la verificare". Testam pe cele ~97.000 de
predictii walk-forward trei reguli, toate pe aceleasi meciuri:

  1. dupa AVANTAJ fata de cota  -- adica exact ce a iesit pe minus in backtest;
  2. dupa INCREDEREA modelului  -- probabilitatea cea mai mare, indiferent de cota;
  3. increderea modelului, dar DOAR unde piata e de acord cu el.

A treia porneste de la o observatie din propriul nostru backtest: cu cat modelul
se indeparteaza mai mult de cota, cu atat greseste mai des. Deci dezacordul mare
nu e semn de valoare, ci de eroare.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from dixon_coles import markets_from_rates
from evaluate import SPLIT, devig

ALPHA = 0.50
# Doar competitiile care vor aparea in aplicatie.
LIGI_AFISATE = {"E0", "E1", "SP1", "I1", "D1", "F1", "N1", "P1", "B1", "ROU_Superliga"}


def probabilitati_toate(d: pd.DataFrame) -> pd.DataFrame:
    """Probabilitatile pentru fiecare piata, din ratele salvate de backtest."""
    lam = np.exp(ALPHA * np.log(d["lam_g"]) + (1 - ALPHA) * np.log(d["lam_s"]))
    mu = np.exp(ALPHA * np.log(d["mu_g"]) + (1 - ALPHA) * np.log(d["mu_s"]))
    randuri = []
    for l, m, r in zip(lam, mu, d["rho"]):
        p = markets_from_rates(float(l), float(m), float(r))
        randuri.append([p["p_home"], p["p_draw"], p["p_away"],
                        p["p_over25"], 1 - p["p_over25"],
                        p["p_btts"], 1 - p["p_btts"]])
    return pd.DataFrame(randuri, columns=["1", "X", "2", "over", "under", "btts", "nobtts"],
                        index=d.index)


def construieste(d: pd.DataFrame) -> pd.DataFrame:
    """Un rand per (meci, piata), cu probabilitate, cota si rezultat."""
    p = probabilitati_toate(d)
    castigat = pd.DataFrame({
        "1": d["result"] == 0, "X": d["result"] == 1, "2": d["result"] == 2,
        "over": d["over25"] == 1, "under": d["over25"] == 0,
        "btts": d["btts"] == 1, "nobtts": d["btts"] == 0,
    }, index=d.index)
    cote = pd.DataFrame({
        "1": d["max_h"], "X": d["max_d"], "2": d["max_a"],
        "over": d["max_o25"], "under": d["max_u25"],
        "btts": np.nan, "nobtts": np.nan,
    }, index=d.index)
    # Cota medie de pe piata: asta apare in aplicatie, nu cea mai buna cota
    # de la vreo casa anume.
    cote_medii = pd.DataFrame({
        "1": d["avg_h"], "X": d["avg_d"], "2": d["avg_a"],
        "over": d["avg_o25"], "under": d["avg_u25"],
        "btts": np.nan, "nobtts": np.nan,
    }, index=d.index)

    # Probabilitatea implicita a pietei, pentru masurarea dezacordului.
    o = d[["psc_h", "psc_d", "psc_a"]].to_numpy(float)
    o = np.where(np.isnan(o), d[["avg_h", "avg_d", "avg_a"]].to_numpy(float), o)
    ok = np.isfinite(o).all(1) & (o > 1).all(1)
    piata = pd.DataFrame(np.nan, index=d.index, columns=["1", "X", "2", "over", "under",
                                                        "btts", "nobtts"])
    piata.loc[ok, ["1", "X", "2"]] = devig(o[ok])
    ou = d[["max_o25", "max_u25"]].to_numpy(float)
    ok_ou = np.isfinite(ou).all(1) & (ou > 1).all(1)
    piata.loc[ok_ou, ["over", "under"]] = devig(ou[ok_ou])

    bucati = []
    for piata_nume in p.columns:
        bucati.append(pd.DataFrame({
            "div": d["div"].to_numpy(), "date": d["date"].to_numpy(),
            "piata": piata_nume,
            "p": p[piata_nume].to_numpy(),
            "cota": cote[piata_nume].to_numpy(),
            "cota_medie": cote_medii[piata_nume].to_numpy(),
            "p_piata": piata[piata_nume].to_numpy(),
            "castigat": castigat[piata_nume].to_numpy(),
        }))
    return pd.concat(bucati, ignore_index=True)


def raport(nume: str, sel: pd.DataFrame, total_meciuri: int) -> None:
    if sel.empty:
        print(f"  {nume:46s} nicio selectie")
        return
    rata = sel["castigat"].mean()
    cu_cota = sel.dropna(subset=["cota"])
    cu_cota = cu_cota[cu_cota["cota"] > 1]
    if len(cu_cota):
        profit = np.where(cu_cota["castigat"], cu_cota["cota"] - 1, -1.0)
        roi = profit.mean()
        se = profit.std(ddof=1) / np.sqrt(len(profit))
        t = roi / se if se > 0 else 0
        roi_txt = f"{roi:+6.2%} (t={t:+5.2f})"
    else:
        roi_txt = "     fara cote"
    pe_zi = len(sel) / max(total_meciuri, 1)
    print(f"  {nume:46s} {len(sel):6,} sel. {rata:6.1%} reusite  ROI {roi_txt}  "
          f"{pe_zi:.2f}/meci")


def main() -> int:
    d = pd.read_csv("out/rates_dual.csv", parse_dates=["date"])
    d = d[(d["date"] >= SPLIT) & (d["div"].isin(LIGI_AFISATE))].reset_index(drop=True)
    print(f"Test pe {len(d):,} meciuri din ligile afisate, 2019-2026\n")

    t = construieste(d)
    t["dezacord"] = t["p"] - t["p_piata"]
    t["avantaj"] = t["p"] * t["cota"] - 1

    print("REGULA 1 — dupa avantajul fata de cota (ce am masurat deja ca pierde):")
    for prag in (0.05, 0.10):
        raport(f"avantaj > {prag:.0%}", t[t["avantaj"] > prag], len(d))

    print("\nREGULA 2 — dupa increderea modelului, indiferent de cota:")
    for prag in (0.55, 0.60, 0.65, 0.70, 0.75):
        raport(f"probabilitate >= {prag:.0%}", t[t["p"] >= prag], len(d))

    print("\nREGULA 3 — increderea modelului, dar numai unde piata e de acord:")
    for prag in (0.60, 0.65, 0.70):
        for tol in (0.05, 0.08):
            sel = t[(t["p"] >= prag) & (t["dezacord"].abs() <= tol)]
            raport(f"probabilitate >= {prag:.0%} si dezacord <= {tol:.0%}", sel, len(d))

    # Regula 3 alege mereu ce e mai sigur, deci ajunge la cote de 1,05-1,25, la
    # care un castig nu acopera o pierdere. Intrebarea practica: daca cerem si
    # o cota minima, ce ramane si cum se comporta?
    print("\nREGULA 4 — acord cu piata, dar numai peste o cota minima:")
    for cota_min in (1.30, 1.45, 1.60, 1.80, 2.00):
        for prag in (0.55, 0.60, 0.65):
            sel = t[(t["p"] >= prag) & (t["dezacord"].abs() <= 0.05)
                    & (t["cota"] >= cota_min)]
            raport(f"cota >= {cota_min:.2f} si probabilitate >= {prag:.0%}", sel, len(d))
        print()

    # Si cat de mult conteaza acordul cu piata cand cerem cote mari: poate
    # filtrul care ajuta la cote mici incurca aici.
    print("REGULA 5 — cota minima, fara filtrul de acord cu piata:")
    for cota_min in (1.45, 1.60, 1.80):
        for prag in (0.55, 0.60):
            sel = t[(t["p"] >= prag) & (t["cota"] >= cota_min)]
            raport(f"cota >= {cota_min:.2f} si probabilitate >= {prag:.0%}", sel, len(d))

    # Pana aici profitul s-a calculat la cota cea mai buna de pe piata. In
    # aplicatie apare cota medie, care e mai mica -- deci masuram si asa,
    # altfel promitem un randament pe care nu-l poti obtine.
    print("\nACELEASI REGULI, DAR LA COTA MEDIE (cea pe care o vede utilizatorul):")
    t_medie = t.copy()
    t_medie["cota"] = t["cota_medie"]
    for cota_min in (1.45, 1.60, 1.80):
        for prag in (0.55, 0.60):
            sel = t_medie[(t_medie["p"] >= prag) & (t_medie["dezacord"].abs() <= 0.05)
                          & (t_medie["cota"] >= cota_min)]
            raport(f"cota medie >= {cota_min:.2f} si probabilitate >= {prag:.0%}",
                   sel, len(d))

    # Ratele pe benzi pentru regula aleasa: ele ajung in aplicatie ca "promis",
    # deci trebuie masurate exact pe regula care se foloseste.
    print("\nBENZI pentru regula propusa (cota medie >= 1.45, p >= 60%, acord <= 5%):")
    sel = t_medie[(t_medie["p"] >= 0.60) & (t_medie["dezacord"].abs() <= 0.05)
                  & (t_medie["cota"] >= 1.45)]
    for jos, sus in ((0.60, 0.65), (0.65, 0.70), (0.70, 0.80), (0.80, 1.01)):
        banda = sel[(sel["p"] >= jos) & (sel["p"] < sus)]
        if len(banda) < 50:
            continue
        profit = np.where(banda["castigat"], banda["cota"] - 1, -1.0)
        print(f"  {jos:.0%}-{sus:.0%}: {len(banda):6,} selectii, "
              f"{banda['castigat'].mean():5.1%} reusite, "
              f"cota medie {banda['cota'].mean():.2f}, ROI {profit.mean():+6.2%}")

    # Banda 65-70% iese mai prost decat 60-65%, ceea ce pare pe dos. Explicatia
    # probabila: cu cota peste 1,45 si model peste 65%, dezacordul e neaparat
    # pozitiv -- adica exact tiparul "value bet" masurat deja ca pierzator.
    print("\nDUPA SEMNUL DEZACORDULUI (cota medie >= 1.45, p >= 60%):")
    baza = t_medie[(t_medie["p"] >= 0.60) & (t_medie["cota"] >= 1.45)]
    for eticheta, sel in (
            ("model sub piata (dezacord negativ)", baza[baza["dezacord"] < 0]),
            ("model peste piata, pana la +2pp", baza[(baza["dezacord"] >= 0)
                                                    & (baza["dezacord"] <= 0.02)]),
            ("model peste piata, +2 pana la +5pp", baza[(baza["dezacord"] > 0.02)
                                                        & (baza["dezacord"] <= 0.05)]),
            ("model peste piata, peste +5pp", baza[baza["dezacord"] > 0.05])):
        raport(eticheta, sel, len(d))

    # Regula care rezulta din toate masuratorile de mai sus: cota utilizabila,
    # model destul de sigur, si NU mai increzator decat piata cu mai mult de
    # doua puncte. Partea de sub piata se lasa larga: acolo ratele sunt cele
    # mai bune.
    print("\nREGULA PROPUSA (cota >= 1.45, p >= 60%, dezacord intre -10pp si +2pp):")
    for eticheta, tabel in (("la cota medie", t_medie), ("la cea mai buna cota", t)):
        sel = tabel[(tabel["p"] >= 0.60) & (tabel["cota"] >= 1.45)
                    & (tabel["dezacord"] <= 0.02) & (tabel["dezacord"] >= -0.10)]
        raport(eticheta, sel, len(d))

    # Pragul de +2pp e prea strict in practica: cu 40 de meciuri pe zi nu trece
    # aproape nimic, fiindca o cota peste 1,45 la un model de 60%+ inseamna
    # aproape sigur ca modelul e peste piata. Masuram pe niveluri, ca fiecare
    # selectie sa poarte rata masurata a nivelului ei.
    print("\n  Pe niveluri de dezacord (cota medie >= 1.45, p >= 60%):")
    baza2 = t_medie[(t_medie["p"] >= 0.60) & (t_medie["cota"] >= 1.45)
                    & (t_medie["dezacord"] >= -0.10)]
    for eticheta, jos, sus in (("model sub piata", -0.10, 0.0),
                               ("0 .. +2pp", 0.0, 0.02),
                               ("+2 .. +5pp", 0.02, 0.05)):
        nivel = baza2[(baza2["dezacord"] >= jos) & (baza2["dezacord"] < sus)]
        if nivel.empty:
            continue
        profit = np.where(nivel["castigat"], nivel["cota"] - 1, -1.0)
        print(f"    {eticheta:<18} {len(nivel):5,} selectii, "
              f"{nivel['castigat'].mean():5.1%} reusite, "
              f"cota medie {nivel['cota'].mean():.2f}, ROI {profit.mean():+6.2%}")

    print("\n  Regula largita (dezacord pana la +5pp):")
    for eticheta, tabel in (("la cota medie", t_medie), ("la cea mai buna cota", t)):
        sel = tabel[(tabel["p"] >= 0.60) & (tabel["cota"] >= 1.45)
                    & (tabel["dezacord"] <= 0.05) & (tabel["dezacord"] >= -0.10)]
        raport(eticheta, sel, len(d))

    print("\n  Pe benzi (la cota medie):")
    sel = t_medie[(t_medie["p"] >= 0.60) & (t_medie["cota"] >= 1.45)
                  & (t_medie["dezacord"] <= 0.02) & (t_medie["dezacord"] >= -0.10)]
    for jos, sus in ((0.60, 0.65), (0.65, 0.70), (0.70, 1.01)):
        banda = sel[(sel["p"] >= jos) & (sel["p"] < sus)]
        if len(banda) < 50:
            continue
        profit = np.where(banda["castigat"], banda["cota"] - 1, -1.0)
        print(f"    {jos:.0%}-{sus:.0%}: {len(banda):5,} selectii, "
              f"{banda['castigat'].mean():5.1%} reusite, "
              f"cota medie {banda['cota'].mean():.2f}, ROI {profit.mean():+6.2%}")

    print("\nPentru comparatie, cat de des se confirma fiecare piata in general:")
    for piata_nume in ("1", "X", "2", "over", "under", "btts", "nobtts"):
        sub = t[t["piata"] == piata_nume]
        print(f"  {piata_nume:8s} {sub['castigat'].mean():5.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
