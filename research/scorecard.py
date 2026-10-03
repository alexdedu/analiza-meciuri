"""Tine socoteala propriilor selectii si verifica daca s-au adeverit.

Pana acum aplicatia arata rate luate dintr-un backtest. Backtestul e o promisiune
despre trecut; fisa asta e o dovada despre prezent. Daca banda de 70-80% incepe
sa dea 55% in realitate, se vede aici, nu in portofel.

Fisierul se comite in repo (`istoric/selectii.json`), nu se tine in cache-ul
CI: cache-ul se poate sterge oricand, iar un istoric care dispare nu e istoric.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ISTORIC = Path(__file__).parent.parent / "istoric" / "selectii.json"

# Ratele masurate in backtest, pentru comparatie cu realitatea.
#
# Benzile de 70% si peste vin de la regula veche, dinainte de cota minima de
# 1,45: nu se mai produc selectii acolo, dar selectiile notate atunci raman in
# evidenta si trebuie comparate cu ce li s-a promis lor.
# Cele doua benzi active sunt masurate pe regula de acum (cota >= 1,45,
# dezacord intre -10 si +2 puncte).
ASTEPTARI = {
    # Nivelurile de acum, dupa cat de departe e modelul de piata.
    "sub piață": 0.653,
    "aproape de piață": 0.632,
    "peste piață": 0.601,
    # Benzile de probabilitate, folosite pana pe 30 septembrie 2026.
    "80% sau peste": 0.882,
    "70-80%": 0.753,
    "65-70%": 0.666,
    "60-65%": 0.636,
}


def _cheie(rec: dict) -> str:
    """Un identificator stabil: acelasi meci si aceeasi piata = aceeasi intrare."""
    return f"{rec['match_id']}|{rec['market']}"


def incarca() -> list[dict]:
    if not ISTORIC.exists():
        return []
    try:
        date = json.loads(ISTORIC.read_text(encoding="utf-8"))
        return date.get("selectii", [])
    except (OSError, json.JSONDecodeError):
        return []


def salveaza(selectii: list[dict]) -> None:
    ISTORIC.parent.mkdir(parents=True, exist_ok=True)
    ISTORIC.write_text(json.dumps({
        "actualizat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selectii": selectii,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def adauga(selectii: list[dict], recomandari: list[dict]) -> list[dict]:
    """Adauga selectiile de azi, fara sa le dubleze pe cele deja notate."""
    existente = {_cheie(s) for s in selectii}
    for r in recomandari:
        if _cheie(r) in existente:
            continue
        selectii.append({
            "cheie": _cheie(r),
            "match_id": r["match_id"],
            "date": r["date"],
            "league_name": r["league_name"],
            "home": r["home"],
            "away": r["away"],
            "market": r["market"],
            "market_label": r["market_label"],
            "probability": r["probability"],
            # Cornerele si cartonasele n-au cota nicaieri: ramane gol, iar
            # bilantul le numara separat, fara profit.
            "odds": r.get("odds"),
            "band": r.get("band") or "cornere/cartonașe",
            "notat_la": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "castigat": None,   # se completeaza dupa meci
            "scor": None,
        })
    return selectii


def _verdict(market: str, hg: int, ag: int) -> bool:
    return {
        "home": hg > ag,
        "draw": hg == ag,
        "away": hg < ag,
        "over25": hg + ag > 2.5,
        "under25": hg + ag < 2.5,
    }[market]


def _verdict_contori(market: str, contori: dict) -> bool | None:
    """Verdictul pentru cornere si cartonase.

    Numele pietei spune totul: "corners_home_over_4.5", "cards_total_under_5.5",
    "corners_more_home". Daca lipseste valoarea din care s-ar vedea (unele
    campionate n-au cornere deloc), intoarce None -- adica "inca nu stim".
    """
    if market == "corners_more_home":
        if contori.get("hc") is None or contori.get("ac") is None:
            return None
        return contori["hc"] > contori["ac"]

    parti = market.split("_")
    if len(parti) != 4:
        return None
    tip, unde, sens, linie = parti
    try:
        prag = float(linie)
    except ValueError:
        return None

    if tip == "corners":
        valori = {"home": contori.get("hc"), "away": contori.get("ac")}
        valori["total"] = (None if valori["home"] is None or valori["away"] is None
                           else valori["home"] + valori["away"])
    elif tip == "cards":
        valori = {"home": contori.get("cy"), "away": contori.get("ca")}
        valori["total"] = (None if valori["home"] is None or valori["away"] is None
                           else valori["home"] + valori["away"])
    else:
        return None

    valoare = valori.get(unde)
    if valoare is None:
        return None
    return valoare > prag if sens == "over" else valoare < prag


def _eticheta_contori(market: str, contori: dict) -> str:
    """Ce s-a intamplat de fapt, pe scurt: "6-3 cornere", "4 cartonase"."""
    if market.startswith("corners"):
        h, a = contori.get("hc"), contori.get("ac")
        return f"{h}-{a} cornere" if h is not None else "—"
    h, a = contori.get("cy"), contori.get("ca")
    return f"{h + a} cartonașe ({h}-{a})" if h is not None and a is not None else "—"


# Meciurile astea nu exista in fisierele football-data: identificatorul lor
# este chiar fixture-ul din API-Football, deci scorul se cere dupa el.
PREFIXE_DUPA_ID = ("EU", "NAT")


def rezolva(selectii: list[dict], hist: pd.DataFrame,
            rezultat_dupa_id=None, scor_extern=None) -> tuple[list[dict], int]:
    """Completeaza rezultatul pentru meciurile care s-au jucat deja.

    Cauta intai in istoricul nostru, apoi, daca acolo nu e nimic, prin
    `scor_extern` -- adica la API-Football, care stie scorul in aceeasi seara,
    nu peste doua zile ca arhivele football-data.
    """
    azi = datetime.now().date()

    def _numar(valoare):
        """Numar intreg, sau None cand campionatul nu are datele astea."""
        return None if valoare is None or pd.isna(valoare) else int(valoare)

    # Cautare rapida dupa (data, gazda, oaspete).
    jucate = {}
    contori = {}
    are_contori = {"hc", "ac", "hy", "ay", "hr", "ar"}.issubset(hist.columns)
    for r in hist.itertuples(index=False):
        cheie = (r.date.strftime("%Y-%m-%d"), r.home, r.away)
        jucate[cheie] = (int(r.hg), int(r.ag))
        if are_contori:
            galbene_rosii = [_numar(getattr(r, c, None))
                             for c in ("hy", "hr", "ay", "ar")]
            contori[cheie] = {
                "hc": _numar(getattr(r, "hc", None)),
                "ac": _numar(getattr(r, "ac", None)),
                "cy": (None if galbene_rosii[0] is None or galbene_rosii[1] is None
                       else galbene_rosii[0] + galbene_rosii[1]),
                "ca": (None if galbene_rosii[2] is None or galbene_rosii[3] is None
                       else galbene_rosii[2] + galbene_rosii[3]),
            }

    noi = 0
    for s in selectii:
        if s["castigat"] is not None:
            continue
        if datetime.fromisoformat(s["date"]).date() >= azi:
            continue  # meciul nu s-a jucat inca

        cheie = (s["date"], s["home"], s["away"])

        # Selectiile pe cornere si cartonase se verifica din alte coloane, si
        # doar din arhiva: API-ul le-ar da, dar ar costa o cerere per meci
        # pentru ceva ce oricum apare in fisiere peste o zi-doua.
        if s["market"].startswith(("corners_", "cards_")):
            valori = contori.get(cheie)
            if not valori:
                continue
            verdict = _verdict_contori(s["market"], valori)
            if verdict is None:
                continue
            s["castigat"] = verdict
            s["scor"] = _eticheta_contori(s["market"], valori)
            s["rezolvat_la"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            noi += 1
            continue

        scor = jucate.get(cheie)
        if (scor is None and rezultat_dupa_id
                and s["match_id"].startswith(PREFIXE_DUPA_ID)):
            scor = rezultat_dupa_id(s["match_id"])
        if scor is None and scor_extern:
            scor = scor_extern(s)
        if scor is None:
            continue

        hg, ag = scor
        s["sursa_scor"] = "istoric" if jucate.get(
            (s["date"], s["home"], s["away"])) else "api"
        s["castigat"] = _verdict(s["market"], hg, ag)
        s["scor"] = f"{hg}-{ag}"
        s["rezolvat_la"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        noi += 1
    return selectii, noi


def _e_contor(s: dict) -> bool:
    return str(s.get("market", "")).startswith(("corners_", "cards_"))


def rezumat(selectii: list[dict]) -> dict:
    """Bilantul, per total si pe benzi, asa cum il vede aplicatia.

    Selectiile pe cornere si cartonase se tin deoparte: n-au cota, deci n-au
    nici profit, iar amestecate cu celelalte ar strica si rata, si randamentul.
    """
    cu_cota = [s for s in selectii if not _e_contor(s)]
    contori = [s for s in selectii if _e_contor(s)]

    rezolvate = [s for s in cu_cota if s["castigat"] is not None]
    reusite = [s for s in rezolvate if s["castigat"]]

    # Profit la miza fixa de o unitate, la cota notata in momentul selectiei.
    profit = sum((s["odds"] - 1) if s["castigat"] else -1.0
                 for s in rezolvate if s.get("odds"))

    contori_rezolvate = [s for s in contori if s["castigat"] is not None]
    contori_reusite = [s for s in contori_rezolvate if s["castigat"]]

    benzi = []
    for banda, asteptat in ASTEPTARI.items():
        ale_benzii = [s for s in rezolvate if s["band"] == banda]
        if not ale_benzii:
            continue
        cate = sum(1 for s in ale_benzii if s["castigat"])
        benzi.append({
            "band": banda,
            "n": len(ale_benzii),
            "hits": cate,
            "rate": round(cate / len(ale_benzii), 4),
            "expected": asteptat,
        })

    return {
        "total": len(cu_cota),
        "resolved": len(rezolvate),
        "pending": len(cu_cota) - len(rezolvate),
        "hits": len(reusite),
        "hit_rate": round(len(reusite) / len(rezolvate), 4) if rezolvate else None,
        "profit_units": round(profit, 2) if rezolvate else None,
        "roi": round(profit / len(rezolvate), 4) if rezolvate else None,
        "by_band": benzi,
        "since": min((s["date"] for s in selectii), default=None),
        # Bilantul separat al pietelor fara cota.
        "counts": {
            "total": len(contori),
            "resolved": len(contori_rezolvate),
            "pending": len(contori) - len(contori_rezolvate),
            "hits": len(contori_reusite),
            "hit_rate": (round(len(contori_reusite) / len(contori_rezolvate), 4)
                         if contori_rezolvate else None),
            # Cat promitea backtestul pentru pietele astea, in banda folosita.
            "expected": 0.65,
        },
    }


# Cate selectii trecute trimitem in aplicatie. Fisierul de istoric creste la
# nesfarsit; ecranul are nevoie doar de ultimele saptamani, iar predictions.json
# se descarca de pe retea de cateva ori pe zi.
LIMITA_ISTORIC = 80


def recente(selectii: list[dict], limita: int = LIMITA_ISTORIC) -> list[dict]:
    """Selectiile pentru ecranul de istoric, cele mai noi intai.

    Le trimitem pe toate, si pe cele nejucate: altfel meciurile de maine ar
    disparea din lista imediat ce ies din fereastra de trei zile a ecranului
    principal, iar utilizatorul n-ar mai sti ce a fost notat.
    """
    ordonate = sorted(selectii,
                      key=lambda s: (s["date"], s.get("notat_la", ""), s["home"]),
                      reverse=True)
    return [{
        "match_id": s["match_id"],
        "date": s["date"],
        "league_name": s["league_name"],
        "home": s["home"],
        "away": s["away"],
        "market_label": s["market_label"],
        "probability": s["probability"],
        "odds": s["odds"],
        "band": s["band"],
        "won": s["castigat"],
        "score": s["scor"],
    } for s in ordonate[:limita]]
