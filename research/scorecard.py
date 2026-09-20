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
ASTEPTARI = {
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
            "odds": r["odds"],
            "band": r["band"],
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


def rezolva(selectii: list[dict], hist: pd.DataFrame,
            rezultat_european=None) -> tuple[list[dict], int]:
    """Completeaza rezultatul pentru meciurile care s-au jucat deja."""
    azi = datetime.now().date()
    # Cautare rapida dupa (data, gazda, oaspete).
    jucate = {}
    for r in hist.itertuples(index=False):
        jucate[(r.date.strftime("%Y-%m-%d"), r.home, r.away)] = (int(r.hg), int(r.ag))

    noi = 0
    for s in selectii:
        if s["castigat"] is not None:
            continue
        if datetime.fromisoformat(s["date"]).date() >= azi:
            continue  # meciul nu s-a jucat inca

        scor = jucate.get((s["date"], s["home"], s["away"]))
        if scor is None and rezultat_european and s["match_id"].startswith("EU"):
            scor = rezultat_european(s["match_id"])
        if scor is None:
            continue

        hg, ag = scor
        s["castigat"] = _verdict(s["market"], hg, ag)
        s["scor"] = f"{hg}-{ag}"
        s["rezolvat_la"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        noi += 1
    return selectii, noi


def rezumat(selectii: list[dict]) -> dict:
    """Bilantul, per total si pe benzi, asa cum il vede aplicatia."""
    rezolvate = [s for s in selectii if s["castigat"] is not None]
    reusite = [s for s in rezolvate if s["castigat"]]

    # Profit la miza fixa de o unitate, la cota notata in momentul selectiei.
    profit = sum((s["odds"] - 1) if s["castigat"] else -1.0 for s in rezolvate)

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
        "total": len(selectii),
        "resolved": len(rezolvate),
        "pending": len(selectii) - len(rezolvate),
        "hits": len(reusite),
        "hit_rate": round(len(reusite) / len(rezolvate), 4) if rezolvate else None,
        "profit_units": round(profit, 2) if rezolvate else None,
        "roi": round(profit / len(rezolvate), 4) if rezolvate else None,
        "by_band": benzi,
        "since": min((s["date"] for s in selectii), default=None),
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
