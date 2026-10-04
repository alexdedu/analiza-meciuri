"""Biletul zilei: cateva selectii combinate intr-un singur pariu.

Picioarele vin numai din selectiile deja afisate -- adica din cele care au
trecut filtrele masurate. Biletul nu inventeaza nimic nou, doar alege.

Doua lucruri trebuie spuse deschis, pentru ca schimba cifrele:

1. Sansele se inmultesc. Patru selectii de cate 64% fac impreuna ~17%: un
   bilet castigator din sase. Asta nu e un defect al modelului, e aritmetica
   oricarui bilet combinat, si apare scrisa in aplicatie.
2. Marja casei se inmulteste si ea. O selectie care la cota medie pierde 2,3%
   pe termen lung pierde, pusa de patru ori intr-un bilet, in jur de 9%.

Picioarele sunt mereu din meciuri diferite: doua piete ale aceluiasi meci
(peste 2.5 goluri si peste 9.5 cornere, de exemplu) nu sunt independente, iar
inmultirea probabilitatilor lor ar minti.

Biletul unei zile, odata facut, nu se mai schimba la rularile urmatoare: un
"bilet al zilei" care se rescrie de patru ori pe zi n-ar mai fi al zilei.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ISTORIC = Path(__file__).parent.parent / "istoric" / "bilete.json"

MAXIM_PICIOARE = 4
MINIM_PICIOARE = 2
ORDINE_FAMILII = ["1x2", "goluri", "cornere", "cartonașe"]


def construieste(meciuri_recomandate: list[dict]) -> dict | None:
    """Biletul, din meciurile deja recomandate. None daca nu sunt destule."""
    # Cel mai probabil picior al fiecarui meci, pe fiecare familie.
    candidati = []
    for m in meciuri_recomandate:
        for p in m["picks"]:
            candidati.append({
                "match_id": m["match_id"], "league_name": m["league_name"],
                "date": m["date"], "time": m.get("time", ""),
                "home": m["home"], "away": m["away"],
                "family": p["family"], "market": p["market"],
                "market_label": p["market_label"],
                "probability": p["probability"],
                "odds": p.get("odds"),
                "fair_odds": p.get("fair_odds") or round(1 / p["probability"], 2),
                "historical_hit_rate": p["historical_hit_rate"],
            })
    candidati.sort(key=lambda c: -c["probability"])

    picioare: list[dict] = []
    meciuri_folosite: set[str] = set()

    # Intai cate un picior din fiecare tip de piata, ca biletul sa fie
    # amestecat -- rezultat, goluri, cornere, cartonase -- cand se poate.
    for familie in ORDINE_FAMILII:
        for c in candidati:
            if c["family"] == familie and c["match_id"] not in meciuri_folosite:
                picioare.append(c)
                meciuri_folosite.add(c["match_id"])
                break

    # Apoi completam cu cele mai probabile ramase, tot din meciuri diferite.
    for c in candidati:
        if len(picioare) >= MAXIM_PICIOARE:
            break
        if c["match_id"] not in meciuri_folosite:
            picioare.append(c)
            meciuri_folosite.add(c["match_id"])

    picioare = picioare[:MAXIM_PICIOARE]
    if len(picioare) < MINIM_PICIOARE:
        return None

    # Ordinea afisata: dupa ora de inceput, cum le-ar urmari cineva.
    picioare.sort(key=lambda p: (p["date"], p["time"]))

    probabilitate = 1.0
    istoric = 1.0
    cota = 1.0
    estimata = False
    for p in picioare:
        probabilitate *= p["probability"]
        istoric *= p["historical_hit_rate"]
        if p["odds"]:
            cota *= p["odds"]
        else:
            # Pentru cornere si cartonase nu exista cote: folosim cota
            # corecta, si spunem ca e estimata.
            cota *= p["fair_odds"]
            estimata = True

    return {
        "date": datetime.now().date().isoformat(),
        "legs": picioare,
        "combined_probability": round(probabilitate, 4),
        # Cat ar iesi un astfel de bilet dupa ratele masurate ale fiecarui
        # picior -- reperul cinstit, nu procentul modelului.
        "expected_hit_rate": round(istoric, 4),
        "combined_odds": round(cota, 2),
        "odds_estimated": estimata,
    }


def _cheie(picior: dict) -> str:
    return f"{picior['match_id']}|{picior['market']}"


def incarca() -> list[dict]:
    if not ISTORIC.exists():
        return []
    try:
        return json.loads(ISTORIC.read_text(encoding="utf-8")).get("bilete", [])
    except (OSError, json.JSONDecodeError):
        return []


def salveaza(bilete: list[dict]) -> None:
    ISTORIC.parent.mkdir(parents=True, exist_ok=True)
    ISTORIC.write_text(json.dumps({
        "actualizat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bilete": bilete,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def biletul_zilei(bilete: list[dict], nou: dict | None) -> tuple[list[dict], dict | None]:
    """Biletul de azi: cel deja facut, daca exista, altfel cel nou."""
    azi = datetime.now().date().isoformat()
    existent = next((b for b in bilete if b["date"] == azi), None)
    if existent:
        return bilete, existent
    if nou is None:
        return bilete, None
    nou = dict(nou, castigat=None)
    return bilete + [nou], nou


def rezolva(bilete: list[dict], selectii: list[dict]) -> list[dict]:
    """Completeaza verdictul biletelor din verdictele picioarelor lor.

    Un picior pierdut pierde biletul imediat; castigat e doar cand au iesit
    toate. Pana atunci, ramane in asteptare.
    """
    verdicte = {s["cheie"]: s.get("castigat") for s in selectii}
    for b in bilete:
        if b.get("castigat") is not None:
            continue
        rezultate = [verdicte.get(_cheie(p)) for p in b["legs"]]
        for p, r in zip(b["legs"], rezultate):
            p["won"] = r
        if any(r is False for r in rezultate):
            b["castigat"] = False
        elif rezultate and all(r is True for r in rezultate):
            b["castigat"] = True
    return bilete


def rezumat(bilete: list[dict]) -> dict:
    rezolvate = [b for b in bilete if b.get("castigat") is not None]
    castigate = [b for b in rezolvate if b["castigat"]]
    return {
        "total": len(bilete),
        "resolved": len(rezolvate),
        "won": len(castigate),
        # Cat ar fi trebuit sa iasa, in medie, dupa ratele masurate.
        "expected": (round(sum(b["expected_hit_rate"] for b in rezolvate)
                           / len(rezolvate), 4) if rezolvate else None),
    }
