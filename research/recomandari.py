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

Completare din 30 septembrie 2026, dupa ce regula a produs numai cote de
1,05-1,25: s-a adaugat o cota minima (1,45) si dezacordul a devenit asimetric.
Masurat pe aceleasi 25.168 de meciuri, regula noua da 2.185 de selectii, 64,3%
reusite, cota medie 1,52. Randamentul ramane negativ la cota medie (-2,3%,
t=-1,45) si pozitiv doar daca prinzi cea mai buna cota de pe piata (+2,3%).
Adica avantajul nu vine din model, ci din locul de unde iei cota.
"""
from __future__ import annotations

PRAG_PROBABILITATE = 0.60
MAXIM_RECOMANDARI = 6

# Cota minima. Fara ea, regula alegea mereu ce era mai sigur si ajungea la cote
# de 1,05-1,25, unde o singura ratare sterge patru reusite. Masurat pe 25.168 de
# meciuri: cu pragul de 1,45 raman 2.185 de selectii, cu 64,3% reusite.
COTA_MINIMA = 1.45

# Dezacordul nu mai e simetric, si asta e cea mai curata relatie gasita in tot
# backtestul. Cu cat modelul se crede mai bun decat piata, cu atat greseste mai
# des (cota peste 1,45, model peste 60%):
#
#   model sub piata           65,3% reusite
#   pana la +2 puncte peste   63,2%
#   +2 .. +5 puncte peste     60,1%   (t = -2,49 la randament)
#   peste +5 puncte           53,5%   (t = -5,27)
#
# Deci lasam larg partea in care modelul e mai prudent decat piata, si taiem
# scurt partea in care se crede mai destept.
DEZACORD_MAXIM_PESTE = 0.05
DEZACORD_MAXIM_SUB = 0.10

# Pragul strict de +2pp s-a dovedit nefolositor in practica: la o cota peste
# 1,45 si un model de peste 60%, modelul e aproape sigur mai increzator decat
# piata, deci intr-o zi cu 40 de meciuri nu trecea nimic. Asa ca lasam pana la
# +5pp, dar fiecare selectie poarta rata masurata a nivelului ei, nu o medie
# comuna care ar ascunde diferenta.
NIVELE = [
    (-DEZACORD_MAXIM_SUB, 0.00, 0.653, "sub piață"),
    (0.00, 0.02, 0.632, "aproape de piață"),
    (0.02, DEZACORD_MAXIM_PESTE, 0.601, "peste piață"),
]


def _nivel(dezacord: float):
    """Rata masurata si eticheta nivelului in care cade dezacordul."""
    for jos, sus, rata, eticheta in NIVELE:
        if jos <= dezacord < sus:
            return rata, eticheta
    return None, None

# Pietele pe care le putem verifica fata de cota. "Ambele inscriu" lipseste
# intentionat: fara cota, modelul s-a dovedit fals de increzator acolo.
PIETE = [
    ("home", "p_home", "home", "Victorie {home}"),
    ("draw", "p_draw", "draw", "Egal"),
    ("away", "p_away", "away", "Victorie {away}"),
    ("over25", "p_over25", "over25", "Peste 2.5 goluri"),
    ("under25", "p_under25", "under25", "Sub 2.5 goluri"),
]

# Benzile de probabilitate au fost inlocuite de nivelurile de dezacord (vezi
# NIVELE mai jos): pe benzi, 65-70% iesea mai prost decat 60-65%, ceea ce parea
# pe dos pana s-a vazut cauza -- la cota mare si incredere mare, dezacordul e
# neaparat pozitiv, adica exact tiparul care pierde.


def _fara_marja(cote: dict, chei: list[str]) -> dict:
    """Probabilitatile pietei, dupa scoaterea marjei casei."""
    valori = [cote.get(k) for k in chei]
    if any(v is None or v <= 1 for v in valori):
        return {}
    invers = [1 / v for v in valori]
    total = sum(invers)
    return {k: v / total for k, v in zip(chei, invers)}


def construieste(meciuri: list[dict], toate: bool = False) -> list[dict]:
    """Recomandarile, ordonate de la cea mai bine platita la cea mai slaba.

    `toate=True` intoarce toti candidatii, fara limita si fara regula "una
    per meci": asa are de unde alege gruparea pe meciuri, care arata deodata
    si rezultatul, si golurile.
    """
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
            if float(cota) < COTA_MINIMA:
                continue  # prea mica ca sa merite riscul
            dezacord = p - piata[cheie]
            rata, eticheta = _nivel(dezacord)
            if rata is None:
                continue  # in afara intervalului masurat

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

    # Ordinea nu mai e dupa incredere, ci dupa cat de bine platesc selectiile
    # cu aceeasi rata masurata: la 64% reusite, o cota de 1,70 valoreaza mult
    # mai mult decat una de 1,46.
    candidati.sort(key=lambda c: -(c["historical_hit_rate"] * c["odds"]))
    if toate:
        return candidati
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


# Gruparea pe meci ----------------------------------------------------------
#
# Lista plata a selectiilor raspundea la intrebarea "ce sa pariez", dar nu si
# la "ce optiuni am la meciul asta". Gruparea le arata pe toate patru -- cine
# castiga, cate goluri, cate cornere, cate cartonase -- ca alegerea sa fie a
# utilizatorului, nu a unei ordonari dintr-un fisier.

FAMILII = {
    "home": "1x2", "draw": "1x2", "away": "1x2",
    "over25": "goluri", "under25": "goluri",
}

ORDINE_FAMILII = ["1x2", "goluri", "cornere", "cartonașe"]
MAXIM_MECIURI = 6
MAXIM_PE_MECI = 3


def _familie(market: str) -> str:
    if market.startswith("corners"):
        return "cornere"
    if market.startswith("cards"):
        return "cartonașe"
    return FAMILII.get(market, "1x2")


def _valoare(pick: dict) -> float:
    """Cat promite o selectie: rata masurata inmultita cu cota (sau cea corecta)."""
    cota = pick.get("odds") or pick.get("fair_odds") or 1.0
    return float(pick.get("historical_hit_rate", 0.0)) * float(cota)


def _cheie_ordine(meci: dict) -> tuple[int, float]:
    """Meciurile cu cote adevarate intai, apoi cele cu cornere si cartonase."""
    cu_cota = [p for p in meci["picks"] if p.get("odds")]
    if cu_cota:
        return (0, -max(_valoare(p) for p in cu_cota))
    return (1, -max(p["probability"] for p in meci["picks"]))


def grupeaza_pe_meci(cu_cota: list[dict], contori: list[dict]) -> list[dict]:
    """Selectiile, adunate pe meci, cu cel mult una per tip de piata."""
    pe_meci: dict[str, dict] = {}

    for pick in list(cu_cota) + list(contori):
        meci = pe_meci.setdefault(pick["match_id"], {
            "match_id": pick["match_id"],
            "league_name": pick["league_name"],
            "date": pick["date"],
            "time": pick.get("time", ""),
            "home": pick["home"],
            "away": pick["away"],
            "picks": {},
        })
        familie = _familie(pick["market"])
        intrare = {
            "family": familie,
            "market": pick["market"],
            "market_label": pick["market_label"],
            "probability": pick["probability"],
            "odds": pick.get("odds"),
            "fair_odds": pick.get("fair_odds") or round(1 / pick["probability"], 2),
            "historical_hit_rate": pick["historical_hit_rate"],
            "band": pick.get("band", ""),
            # Cat s-a miscat cota de la prima observatie (pozitiv = a scazut).
            "odds_movement": pick.get("odds_movement"),
        }
        # Daca o familie are doua selectii la acelasi meci, o pastram pe cea
        # care promite mai mult.
        existent = meci["picks"].get(familie)
        if existent is None or _valoare(intrare) > _valoare(existent):
            meci["picks"][familie] = intrare

    meciuri = []
    for meci in pe_meci.values():
        picks = sorted(meci["picks"].values(),
                       key=lambda p: ORDINE_FAMILII.index(p["family"]))
        meci["picks"] = picks[:MAXIM_PE_MECI]
        meci["best"] = max(_valoare(p) for p in meci["picks"])
        meciuri.append(meci)

    # Intai meciurile cu selectii pe piete care au cota adevarata: acolo
    # modelul a trecut si filtrul de acord cu piata, deci selectia e verificata
    # de doua ori. Abia apoi cele care au numai cornere si cartonase, unde
    # "cota corecta" e calculata din propriul nostru procent -- a le pune la
    # intrecere dupa aceeasi masura ar fi o comparatie masluita.
    meciuri.sort(key=_cheie_ordine)
    for meci in meciuri:
        meci.pop("best", None)
    return meciuri[:MAXIM_MECIURI]
