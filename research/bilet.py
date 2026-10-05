"""Biletul zilei: cateva selectii combinate intr-un singur pariu.

Picioarele vin numai din selectii care au trecut filtrele masurate -- biletul
nu inventeaza nimic nou, doar alege si combina.

Regulile, cu motivul fiecareia:

- Doar meciuri din urmatoarele trei zile (azi, maine, poimaine). La meciurile
  mai indepartate casele n-au inca piete pe cornere si cartonase, iar un bilet
  care nu se poate juca nu e bilet.
- Cota totala de cel putin 10. Picioarele se aleg ca sa ajunga acolo cu sansa
  cea mai mare: dupa rata masurata inmultita cu cota, nu dupa increderea
  modelului. Asa se ajunge la 10 cu cat mai putine si mai sigure picioare.
- La cornere si cartonase cota reala nu exista in nicio sursa, deci folosim cota
  corecta scazuta cu o marja tipica de casa (7%). Pragul de 10 se verifica pe
  cota asta prudenta, ca biletul real sa nu iasa sub 10.
- Picioarele sunt mereu din meciuri diferite: doua piete ale aceluiasi meci nu
  sunt independente, iar inmultirea sanselor lor ar minti.
- Cel mult trei picioare din acelasi tip de piata, ca biletul sa ramana
  amestecat: rezultat, goluri, cornere, cartonase.

Ce trebuie spus deschis: la cota 10, sansa unui bilet e in jur de 10%. Un bilet
castigator din zece, pe termen lung. Asta e aritmetica oricarui bilet de cota
10, nu un defect al modelului, si apare scrisa in aplicatie.

Biletul unei zile, odata facut, nu se mai schimba la rularile urmatoare -- doar
daca s-au schimbat regulile, si atunci e marcat ca atare.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ISTORIC = Path(__file__).parent.parent / "istoric" / "bilete.json"

# Versiunea regulilor. Un bilet facut azi cu alte reguli se reface.
REGULI = "3-zile-cota-10"

ZILE = 3                 # azi, maine, poimaine
COTA_MINIMA = 10.0
MARJA_CASA = 0.07        # cat scade, tipic, cota unei case fata de cea corecta
MAXIM_PICIOARE = 8
MAXIM_PE_FAMILIE = 3
ORDINE_FAMILII = ["1x2", "goluri", "cornere", "cartonașe"]


def _familie(market: str) -> str:
    if market.startswith("corners"):
        return "cornere"
    if market.startswith("cards"):
        return "cartonașe"
    if market in ("over25", "under25"):
        return "goluri"
    return "1x2"


def _cota_efectiva(p: dict) -> float:
    """Cota reala, sau cea corecta scazuta cu marja casei cand reala lipseste."""
    if p.get("odds"):
        return float(p["odds"])
    corecta = p.get("fair_odds") or 1 / float(p["probability"])
    return float(corecta) * (1 - MARJA_CASA)


def _alege(eligibili: list[dict], limita_familie: bool) -> tuple[list[dict], float]:
    """Picioarele, in ordinea valorii, pana la cota minima."""
    picioare: list[dict] = []
    meciuri: set[str] = set()
    pe_familie: dict[str, int] = {}
    cota = 1.0
    for p in eligibili:
        if cota >= COTA_MINIMA or len(picioare) >= MAXIM_PICIOARE:
            break
        if p["match_id"] in meciuri:
            continue
        if limita_familie and pe_familie.get(p["family"], 0) >= MAXIM_PE_FAMILIE:
            continue
        picioare.append(p)
        meciuri.add(p["match_id"])
        pe_familie[p["family"]] = pe_familie.get(p["family"], 0) + 1
        cota *= p["estimated_odds"]
    return picioare, cota


def construieste(candidati: list[dict], azi: date | None = None) -> dict | None:
    """Biletul, din toate selectiile care trec filtrele. None daca nu se poate.

    `candidati` sunt selectiile plate: cele cu cota (rezultat, goluri) si cele
    pe cornere si cartonase, fiecare cu meciul ei.
    """
    azi = azi or datetime.now().date()
    pana = azi + timedelta(days=ZILE - 1)

    eligibili = []
    for c in candidati:
        zi = date.fromisoformat(c["date"])
        if not (azi <= zi <= pana):
            continue  # prea departe: casele n-au inca toate pietele
        cota = _cota_efectiva(c)
        if cota <= 1.0:
            continue
        eligibili.append({
            "match_id": c["match_id"], "league_name": c["league_name"],
            "date": c["date"], "time": c.get("time", ""),
            "home": c["home"], "away": c["away"],
            "family": _familie(c["market"]), "market": c["market"],
            "market_label": c["market_label"],
            "probability": c["probability"],
            "odds": c.get("odds"),
            "fair_odds": c.get("fair_odds") or round(1 / c["probability"], 2),
            "estimated_odds": round(cota, 2),
            "historical_hit_rate": c["historical_hit_rate"],
        })

    # Ce valoreaza un picior: cat iese istoric, inmultit cu cat plateste. La o
    # cota tinta data, biletul cu valoarea cea mai mare e cel cu sansa cea mai
    # mare de a iesi.
    eligibili.sort(key=lambda p: -(p["historical_hit_rate"] * p["estimated_odds"]))

    picioare, cota = _alege(eligibili, limita_familie=True)
    if cota < COTA_MINIMA:
        # Amestecul e de dorit, dar nu cu pretul biletului: daca limita pe
        # tip de piata il impiedica sa ajunga la 10, renuntam la ea.
        picioare, cota = _alege(eligibili, limita_familie=False)
    if cota < COTA_MINIMA:
        return None  # nu sunt destule selectii apropiate pentru cota 10

    # Ordinea afisata: dupa ora de inceput, cum le-ar urmari cineva.
    picioare.sort(key=lambda p: (p["date"], p["time"]))

    probabilitate = 1.0
    istoric = 1.0
    for p in picioare:
        probabilitate *= p["probability"]
        istoric *= p["historical_hit_rate"]

    return {
        "date": azi.isoformat(),
        "rules": REGULI,
        "legs": picioare,
        "combined_probability": round(probabilitate, 4),
        # Cat ar iesi un astfel de bilet dupa ratele masurate ale fiecarui
        # picior -- reperul cinstit, nu procentul modelului.
        "expected_hit_rate": round(istoric, 4),
        "combined_odds": round(cota, 2),
        "odds_estimated": any(p["odds"] is None for p in picioare),
    }


def de_ce_lipseste(candidati: list[dict], azi: date | None = None) -> dict:
    """Cand nu iese bilet: cat s-ar putea atinge cu ce exista acum.

    In pauzele competitionale, in urmatoarele trei zile se joaca doar
    nationale, iar selectiile care trec filtrele sunt putine. Aplicatia trebuie
    sa spuna asta cu cifre, nu sa ascunda pur si simplu biletul.
    """
    azi = azi or datetime.now().date()
    pana = azi + timedelta(days=ZILE - 1)
    cea_mai_buna: dict[str, float] = {}
    for c in candidati:
        zi = date.fromisoformat(c["date"])
        if not (azi <= zi <= pana):
            continue
        cota = _cota_efectiva(c)
        cea_mai_buna[c["match_id"]] = max(cea_mai_buna.get(c["match_id"], 1.0), cota)

    cota_maxima = 1.0
    for cota in sorted(cea_mai_buna.values(), reverse=True)[:MAXIM_PICIOARE]:
        cota_maxima *= cota

    # Prima zi in care ar intra in fereastra meciuri cu selectii destule.
    viitoare = sorted({c["date"] for c in candidati
                       if date.fromisoformat(c["date"]) > pana})
    return {
        "max_odds": round(cota_maxima, 2),
        "legs_available": len(cea_mai_buna),
        "min_odds": COTA_MINIMA,
        "days": ZILE,
        # Ziua din care biletul ar putea include urmatoarea etapa.
        "next_possible": ((date.fromisoformat(viitoare[0]) - timedelta(days=ZILE - 1))
                          .isoformat() if viitoare else None),
    }


def biletul_zilei(bilete: list[dict], nou: dict | None) -> tuple[list[dict], dict | None]:
    """Biletul de azi: cel deja facut, daca exista si e dupa regulile de acum."""
    azi = datetime.now().date().isoformat()
    de_azi = [b for b in bilete if b["date"] == azi]
    actual = next((b for b in de_azi if b.get("rules") == REGULI), None)
    if actual:
        return bilete, actual
    # Facute azi dupa reguli vechi: le inlocuim, dar nu le stergem din evidenta
    # pe tacute -- raman, marcate ca inlocuite, si nu mai intra in bilant.
    for b in de_azi:
        b["inlocuit"] = True
    if nou is None:
        return bilete, None
    nou = dict(nou, castigat=None)
    return bilete + [nou], nou


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
    # Un bilet inlocuit in aceeasi zi nu mai e "biletul zilei": altfel ziua
    # ar fi numarata de doua ori.
    bilete = [b for b in bilete if not b.get("inlocuit")]
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
