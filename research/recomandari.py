"""Alege automat cateva pariuri din meciurile afisate.

Regula nu e inventata: a fost masurata pe 25.168 de meciuri din 2019-2026
(backtest_recomandari.py). Rezultatele au aratat trei lucruri:

  1. Selectia dupa AVANTAJ fata de cota -- ce ar face oricine intuitiv -- da
     31,5% reusite si randament negativ. Nu o folosim.
  2. Selectia dupa increderea modelului da rate care se confirma, dar doar cand
     exista o cota cu care sa confruntam. La pietele fara cota (ambele inscriu),
     modelul spune 80% si se intampla in 59,8% din cazuri.
  3. Cea mai buna regula: incredere mare SI acord cu piata. Unde modelul si
     cotele spun acelasi lucru, rezultatul se confirma peste asteptari.

Deci: recomandam doar piete cu cota disponibila, unde modelul e sigur si nu
contrazice piata. Nu sunt "pariuri castigatoare" -- sunt meciurile cele mai
previzibile, cu rata istorica scrisa langa fiecare.
"""
from __future__ import annotations

PRAG_PROBABILITATE = 0.60
DEZACORD_MAXIM = 0.05
MAXIM_RECOMANDARI = 6

# Pietele pe care le putem verifica fata de cota. "Ambele inscriu" lipseste
# intentionat: fara cota, modelul s-a dovedit fals de increzator acolo.
PIETE = [
    ("home", "p_home", "home", "Victorie {home}"),
    ("draw", "p_draw", "draw", "Egal"),
    ("away", "p_away", "away", "Victorie {away}"),
    ("over25", "p_over25", "over25", "Peste 2.5 goluri"),
    ("under25", "p_under25", "under25", "Sub 2.5 goluri"),
]

# Rate de reusita masurate pe benzi, pentru selectii cu acordul pietei.
BENZI = [
    (0.80, 1.01, 0.882, "80% sau peste"),
    (0.70, 0.80, 0.753, "70-80%"),
    (0.65, 0.70, 0.666, "65-70%"),
    (0.60, 0.65, 0.636, "60-65%"),
]


def _fara_marja(cote: dict, chei: list[str]) -> dict:
    """Probabilitatile pietei, dupa scoaterea marjei casei."""
    valori = [cote.get(k) for k in chei]
    if any(v is None or v <= 1 for v in valori):
        return {}
    invers = [1 / v for v in valori]
    total = sum(invers)
    return {k: v / total for k, v in zip(chei, invers)}


def _banda(p: float):
    for lo, hi, rata, eticheta in BENZI:
        if lo <= p < hi:
            return rata, eticheta
    return None, None


def construieste(meciuri: list[dict]) -> list[dict]:
    """Recomandarile, ordonate de la cea mai sigura la cea mai putin sigura."""
    candidati = []

    for m in meciuri:
        # Fara date solide despre ambele echipe nu recomandam nimic.
        if m.get("confidence") != "ridicata":
            continue
        cote = m.get("reference_odds") or {}
        piata_1x2 = _fara_marja(cote, ["home", "draw", "away"])
        piata_ou = _fara_marja(cote, ["over25", "under25"])

        for cheie, cheie_prob, cheie_cota, sablon in PIETE:
            piata = piata_1x2 if cheie in ("home", "draw", "away") else piata_ou
            if cheie not in piata:
                continue  # fara cota nu avem cu ce verifica
            p = m["probs"].get(cheie_prob)
            cota = cote.get(cheie_cota)
            if p is None or cota is None or p < PRAG_PROBABILITATE:
                continue
            dezacord = p - piata[cheie]
            if abs(dezacord) > DEZACORD_MAXIM:
                continue
            rata, eticheta = _banda(p)
            if rata is None:
                continue

            candidati.append({
                "match_id": m["id"],
                "league_name": m["league_name"],
                "date": m["date"],
                "time": m["time"],
                "home": m["home"],
                "away": m["away"],
                "market": cheie,
                "market_label": sablon.format(home=m["home"], away=m["away"]),
                "probability": round(p, 4),
                "odds": round(float(cota), 2),
                "market_probability": round(piata[cheie], 4),
                "disagreement": round(dezacord, 4),
                "band": eticheta,
                "historical_hit_rate": rata,
            })

    candidati.sort(key=lambda c: -c["probability"])
    alese = candidati[:MAXIM_RECOMANDARI]

    # Un singur meci nu trebuie sa ocupe toata lista cu trei piete ale lui.
    vazute: dict[str, int] = {}
    filtrate = []
    for c in alese if len(candidati) <= MAXIM_RECOMANDARI else candidati:
        if vazute.get(c["match_id"], 0) >= 1:
            continue
        vazute[c["match_id"]] = vazute.get(c["match_id"], 0) + 1
        filtrate.append(c)
        if len(filtrate) >= MAXIM_RECOMANDARI:
            break
    return filtrate
