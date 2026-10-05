"""Urmareste cum se misca cota fiecarei selectii, de la prima observatie.

Masurat in backtest_miscare_cote.py, pe 3.695 de selectii ale regulii de acum:

  cota a scazut peste 5%     63,3% reusite   la cota de deschidere: +4,5%
  aproape neschimbata        63,7%
  cota a crescut peste 5%    58,9% reusite   -8,6% randament (t = -1,93)

Pe toate pietele, fara regula noastra, acelasi tipar e mult mai apasat: un
rezultat a carui cota creste cu peste 5% iese in 31% din cazuri si pierde
10,7% chiar la cota de inchidere (t = -10,05). Piata stie ceva.

De aici doua reguli:
1. Selectiile a caror cota a crescut cu peste 5% de cand le-am vazut prima
   data ies din lista: banii au plecat de la ele.
2. Cand cota scade, valoarea era in pretul de la inceput -- deci aplicatia
   spune asta, ca selectia sa fie pusa devreme, nu chiar inainte de meci.

Fisierul tine doar zilele dinaintea meciului, deci sta in `research/data`
(cache-ul CI), nu in istoricul comis: daca se pierde, se pierde doar punctul
de pornire al masuratorii, nu ceva ce n-ar mai putea fi refacut.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

FISIER = Path(__file__).parent / "data" / "cote_urmarite.json"

# Prag masurat: peste el, cresterea cotei inseamna rezultat mai rar.
CRESTERE_MAXIMA = 0.05
PASTRARE_ZILE = 10


def _cheie(pick: dict) -> str:
    return f"{pick['match_id']}|{pick['market']}"


def incarca() -> dict:
    if not FISIER.exists():
        return {}
    try:
        return json.loads(FISIER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def salveaza(urmarite: dict) -> None:
    FISIER.parent.mkdir(parents=True, exist_ok=True)
    FISIER.write_text(json.dumps(urmarite, ensure_ascii=False, indent=0),
                      encoding="utf-8")


def actualizeaza(picks: list[dict], urmarite: dict,
                 acum: datetime | None = None) -> dict:
    """Noteaza cota de la prima observatie si calculeaza miscarea de atunci.

    Pozitiv = cota a scazut (au intrat bani pe rezultat); negativ = a crescut.
    """
    acum = acum or datetime.now(timezone.utc)
    for p in picks:
        cota = p.get("odds")
        if not cota:
            continue  # cornere si cartonase: n-au cota de urmarit
        cheie = _cheie(p)
        if cheie not in urmarite:
            urmarite[cheie] = {"first": float(cota), "seen": acum.isoformat(),
                               "date": p.get("date")}
        prima = urmarite[cheie]["first"]
        p["odds_first"] = prima
        p["odds_movement"] = round(prima / float(cota) - 1, 4)

    # Meciurile jucate de mult nu mai au ce cauta aici.
    limita = (acum - timedelta(days=PASTRARE_ZILE)).date().isoformat()
    return {k: v for k, v in urmarite.items() if (v.get("date") or "9999") >= limita}


def a_fugit_piata(pick: dict) -> bool:
    """Adevarat cand cota a crescut prea mult de cand am vazut-o prima data."""
    return pick.get("odds_movement", 0.0) < -CRESTERE_MAXIMA
