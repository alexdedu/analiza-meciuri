"""Cornere si cartonase pentru meciurile afisate.

Se adauga peste predictiile existente, doar la meciurile din cele 12
campionate care au datele astea in arhiva. Feedul suplimentar (Romania si
celelalte 18 tari) nu contine nici cornere, nici cartonase, iar cupele si
nationalele vin de la alta sursa -- acolo sectiunea lipseste pur si simplu.

Ce s-a masurat inainte (backtest_counts.py, 16.676 de meciuri neatinse la
antrenare, castig fata de rata de baza in unitati de log-loss):

  cine da mai multe cornere   +0,037   informativ
  cornere pe echipa           +0,024   informativ
  cartonase pe meci           +0,013   slab informativ
  cartonase pe echipa         +0,010   slab informativ
  cornere pe meci (total)      0,000   NU stie mai mult decat media

Ultima linie e motivul pentru care totalul de cornere apare in aplicatie cu
avertisment, iar niciuna dintre pietele astea nu intra in selectiile automate:
pentru ele nu exista cote istorice cu care sa verificam regula de selectie, iar
ultima data cand am afisat o piata neverificata ("ambele inscriu"), modelul
spunea 80% acolo unde realitatea era 59,8%.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import counts_model

XI = 0.0025             # aceeasi uitare ca in backtest
FEREASTRA_ZILE = 1095
MINIM_MECIURI = 300

LINII = {
    "corners": {"total": [8.5, 9.5, 10.5, 11.5], "echipa": [3.5, 4.5, 5.5]},
    "cards": {"total": [2.5, 3.5, 4.5, 5.5], "echipa": [1.5, 2.5]},
}

# Cat de mult stie modelul, in unitati de log-loss fata de rata de baza.
# Cifrele vin din backtest_counts.py si ajung ca atare in aplicatie.
CALITATE = {
    "corners_total": {"gain": 0.000, "label": "cat media campionatului"},
    "corners_team": {"gain": 0.037, "label": "informativ"},
    "corners_winner": {"gain": 0.052, "label": "cel mai informativ"},
    "cards_total": {"gain": 0.022, "label": "slab informativ"},
    "cards_team": {"gain": 0.016, "label": "slab informativ"},
}

# Cat de mult trebuie trasa fiecare piata catre media campionatului ca
# promisiunea sa se potriveasca cu realitatea. Masurat in backtest_counts.py:
# fara corectie, modelul promitea 82% si livra 74%; cu ea, eroarea scade sub
# doua puncte. Valorile sunt mediana pe cele 12 campionate.
#
# Cat de mic e numarul, cu atat mai putin stie modelul: la totalul de cornere
# (0,43) aproape ca nu mai ramane nimic din predictie, ceea ce se potriveste cu
# faptul masurat ca acolo nu bate media campionatului.
GAMMA = {
    "corners_total": 0.43,
    "corners_team": 0.79,
    "corners_winner": 0.80,
    "cards_total": 0.47,
    "cards_team": 0.56,
}


def _coloane(tip: str) -> tuple[str, str]:
    return ("hc", "ac") if tip == "corners" else ("cy", "ca")


def pregateste(hist: pd.DataFrame) -> pd.DataFrame:
    """Adauga coloanele de cartonase totale (galbene + rosii) pe fiecare parte."""
    numeric = {c: pd.to_numeric(hist[c], errors="coerce")
               for c in ("hy", "ay", "hr", "ar")}
    return hist.assign(cy=numeric["hy"] + numeric["hr"],
                       ca=numeric["ay"] + numeric["ar"])


def _fit_liga(liga: pd.DataFrame, coloane: tuple[str, str], azi: pd.Timestamp):
    """Modelul unui campionat plus dispersia totalurilor, ambele doar din trecut."""
    train = liga[(liga["date"] < azi)
                 & (liga["date"] >= azi - pd.Timedelta(days=FEREASTRA_ZILE))]
    train = train.dropna(subset=list(coloane))
    if len(train) < MINIM_MECIURI:
        return None

    echipe = sorted(set(train["home"]) | set(train["away"]))
    idx = {t: k for k, t in enumerate(echipe)}
    varste = (azi - train["date"]).dt.days.to_numpy(dtype=float)
    fit = counts_model.fit_counts(
        train["home"].map(idx).to_numpy(), train["away"].map(idx).to_numpy(),
        train[coloane[0]].to_numpy(dtype=float),
        train[coloane[1]].to_numpy(dtype=float),
        np.exp(-XI * varste), len(echipe), idx)

    # Dispersia, separat pe total si pe fiecare parte: Poisson presupune ca
    # varianta e egala cu media, iar la cornere nu e -- de acolo venea
    # increderea umflata.
    serii = {"total": ([], []), "home": ([], []), "away": ([], [])}
    for r in train.itertuples(index=False):
        rate = fit.rates(r.home, r.away)
        if not rate:
            continue
        h_obs = float(getattr(r, coloane[0]))
        a_obs = float(getattr(r, coloane[1]))
        for cheie, medie, observat in (("total", rate[0] + rate[1], h_obs + a_obs),
                                       ("home", rate[0], h_obs),
                                       ("away", rate[1], a_obs)):
            serii[cheie][0].append(medie)
            serii[cheie][1].append(observat)
    if len(serii["total"][0]) < 200:
        return None

    dispersii = {cheie: counts_model.fit_dispersie(np.array(m), np.array(o))
                 for cheie, (m, o) in serii.items()}
    # Ratele de baza ale campionatului, pentru calibrare.
    baze = {
        "total": {linie: float(np.mean(np.array(serii["total"][1]) > linie))
                  for linie in LINII[tip_din_coloane(coloane)]["total"]},
        "home": {linie: float(np.mean(np.array(serii["home"][1]) > linie))
                 for linie in LINII[tip_din_coloane(coloane)]["echipa"]},
        "away": {linie: float(np.mean(np.array(serii["away"][1]) > linie))
                 for linie in LINII[tip_din_coloane(coloane)]["echipa"]},
        "winner": float(np.mean(np.array(serii["home"][1])
                                > np.array(serii["away"][1]))),
    }
    return fit, dispersii, len(train), baze


def tip_din_coloane(coloane: tuple[str, str]) -> str:
    return "corners" if coloane[0] == "hc" else "cards"


def _piete(fit, dispersii: dict, baze: dict, tip: str,
           gazda: str, oaspete: str) -> dict | None:
    rate = fit.rates(gazda, oaspete)
    if rate is None:
        return None
    lam, mu = rate

    dist = {
        "total": counts_model.nb_pmf(lam + mu, dispersii["total"]),
        "home": counts_model.nb_pmf(lam, dispersii["home"]),
        "away": counts_model.nb_pmf(mu, dispersii["away"]),
    }

    def calibrat(p: float, familie: str, baza: float) -> float:
        return round(float(counts_model.calibreaza(p, baza, GAMMA[familie])), 4)

    out = {
        "expected": {"home": round(lam, 2), "away": round(mu, 2),
                     "total": round(lam + mu, 2)},
        "total": [{"line": linie,
                   "over": calibrat(counts_model.peste(dist["total"], linie),
                                    f"{tip}_total", baze["total"][linie]),
                   "under": round(1 - calibrat(
                       counts_model.peste(dist["total"], linie),
                       f"{tip}_total", baze["total"][linie]), 4)}
                  for linie in LINII[tip]["total"]],
        "home": [{"line": linie,
                  "over": calibrat(counts_model.peste(dist["home"], linie),
                                   f"{tip}_team", baze["home"][linie])}
                 for linie in LINII[tip]["echipa"]],
        "away": [{"line": linie,
                  "over": calibrat(counts_model.peste(dist["away"], linie),
                                   f"{tip}_team", baze["away"][linie])}
                 for linie in LINII[tip]["echipa"]],
    }
    if tip == "corners":
        brut = counts_model.cine_mai_multe(lam, mu, dispersii["home"],
                                           dispersii["away"])
        gazda_cal = calibrat(brut["home"], "corners_winner", baze["winner"])
        oaspete_cal = calibrat(brut["away"], "corners_winner",
                               1 - baze["winner"] - brut["draw"])
        out["winner"] = {
            "home": gazda_cal,
            "away": oaspete_cal,
            "draw": round(max(1 - gazda_cal - oaspete_cal, 0.0), 4),
        }
    return out


def imbogateste(meciuri: list[dict], hist: pd.DataFrame) -> int:
    """Adauga `extra_markets` la meciurile pentru care avem datele necesare."""
    if not meciuri:
        return 0
    hist = pregateste(hist)
    azi = pd.Timestamp(pd.Timestamp.now().date())

    # Un fit per campionat si tip, refolosit pentru toate meciurile lui.
    cache: dict[tuple[str, str], object] = {}
    imbogatite = 0

    for m in meciuri:
        div = m.get("league")
        if not div or div.startswith(("EU_", "NAT_")):
            continue  # cupe si nationale: alta sursa, fara cornere si cartonase

        extra = {}
        for tip in ("corners", "cards"):
            cheie = (div, tip)
            if cheie not in cache:
                liga = hist[hist["div"] == div]
                cache[cheie] = _fit_liga(liga, _coloane(tip), azi) if not liga.empty else None
            pregatit = cache[cheie]
            if pregatit is None:
                continue
            fit, dispersii, n_train, baze = pregatit
            piete = _piete(fit, dispersii, baze, tip, m["home"], m["away"])
            if piete:
                piete["sample"] = n_train
                extra[tip] = piete

        if extra:
            extra["quality"] = CALITATE
            m["extra_markets"] = extra
            imbogatite += 1

    return imbogatite


# Selectii pe cornere si cartonase ------------------------------------------
#
# Pietele de aici NU au cote nicaieri: nici in arhive, nici la casele din API
# (am verificat 110 tipuri de pariuri pentru meciurile viitoare -- niciunul pe
# cornere sau cartonase). Deci filtrul care face selectiile de la 1X2 sa tina,
# acordul cu piata, nu se poate aplica. Ramane doar increderea modelului, iar
# ea a fost verificata direct: dupa calibrare, la selectiile de peste 65%,
# realitatea a fost cu cel mult doua puncte sub promisiune.
#
# Pietele din care se poate alege, cu rata masurata in banda 60-70% pe 16.676
# de meciuri neatinse la antrenare. Lipsesc, pentru ca acolo promisiunea s-a
# abatut de realitate cu mai mult de doua puncte:
#   cornere peste 5.5 pe echipa (-2,7 si -8,1), "mai multe cornere" la oaspeti
#   (-4,9), cartonase peste 2.5 pe echipa (-5,3 si -3,9), cartonase peste 4.5
#   si peste 5.5 pe meci (-3,5 si -3,6), si sub 3.5 (-4,6).
# Lipseste si totalul de cornere, desi calibrarea lui e buna: acolo modelul nu
# bate media campionatului, deci "selectia" ar fi media imbracata in procent.
PIETE_VERIFICATE = {
    "corners_more_home": 0.649,
    "corners_home_over_3.5": 0.665,
    "corners_home_over_4.5": 0.642,
    "corners_away_over_3.5": 0.649,
    "corners_away_over_4.5": 0.642,
    "cards_total_over_2.5": 0.671,
    "cards_total_over_3.5": 0.637,
    "cards_total_under_4.5": 0.642,
    "cards_total_under_5.5": 0.671,
    "cards_home_over_1.5": 0.649,
    "cards_away_over_1.5": 0.666,
}

# Zona in care o cota ar avea sens: cota corecta intre 1,43 si 1,67. Peste
# plafon pariul e aproape sigur, dar n-ar plati nimic.
PRAG_SELECTIE = 0.60
PLAFON_SELECTIE = 0.70
MAXIM_SELECTII = 4


def _candidat(m: dict, cheie: str, eticheta: str, p: float) -> dict | None:
    rata = PIETE_VERIFICATE.get(cheie)
    if rata is None or not (PRAG_SELECTIE <= p <= PLAFON_SELECTIE):
        return None
    return {
        "match_id": m["id"], "league_name": m["league_name"],
        "date": m["date"], "time": m.get("time", ""),
        "home": m["home"], "away": m["away"],
        "market": cheie, "market_label": eticheta,
        "probability": round(float(p), 4),
        # Cota la care pariul ar fi corect. Pentru pietele astea nu exista cote
        # in nicio sursa, deci reperul e tot ce putem da: daca gasesti mai mult
        # de atat la casa ta, pariul are sens; daca mai putin, nu.
        "fair_odds": round(1 / float(p), 2),
        "historical_hit_rate": rata,
    }


def selectii(meciuri: list[dict], toate: bool = False) -> list[dict]:
    """Ce ar alege modelul pe cornere si cartonase, dintre pietele verificate.

    `toate=True` intoarce toti candidatii, pentru gruparea pe meciuri.
    """
    candidati = []

    for m in meciuri:
        extra = m.get("extra_markets") or {}
        cornere = extra.get("corners") or {}
        cartonase = extra.get("cards") or {}

        castigator = cornere.get("winner") or {}
        if castigator.get("home"):
            candidati.append(_candidat(
                m, "corners_more_home",
                f"{m['home']} — mai multe cornere", castigator["home"]))

        for parte, nume in (("home", m["home"]), ("away", m["away"])):
            for linie in cornere.get(parte, []):
                candidati.append(_candidat(
                    m, f"corners_{parte}_over_{linie['line']}",
                    f"{nume} peste {linie['line']} cornere", linie["over"]))
            for linie in cartonase.get(parte, []):
                candidati.append(_candidat(
                    m, f"cards_{parte}_over_{linie['line']}",
                    f"{nume} peste {linie['line']} cartonașe", linie["over"]))

        for linie in cartonase.get("total", []):
            candidati.append(_candidat(
                m, f"cards_total_over_{linie['line']}",
                f"peste {linie['line']} cartonașe în meci", linie["over"]))
            candidati.append(_candidat(
                m, f"cards_total_under_{linie['line']}",
                f"sub {linie['line']} cartonașe în meci", linie["under"]))

    candidati = [c for c in candidati if c]
    # Cele mai sigure intai, si cel mult una per meci: altfel un singur meci
    # dezechilibrat ar umple lista cu variatiuni ale aceluiasi pariu.
    candidati.sort(key=lambda c: -c["probability"])
    if toate:
        return candidati
    vazute: set[str] = set()
    alese = []
    for c in candidati:
        if c["match_id"] in vazute:
            continue
        vazute.add(c["match_id"])
        alese.append(c)
        if len(alese) >= MAXIM_SELECTII:
            break
    return alese
